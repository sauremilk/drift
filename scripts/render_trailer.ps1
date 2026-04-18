<#
.SYNOPSIS
    Render the "All Green. All Wrong." trailer for drift-analyzer.

.DESCRIPTION
    Master orchestrator that:
    1. Renders terminal scenes via Pillow + ffmpeg -> MP4
    2. Renders text-card scenes via Pillow + ffmpeg -> MP4
    3. Concatenates all 13 scene clips into the final trailer MP4

    Prerequisites: ffmpeg, .venv with Pillow + Rich installed.

.EXAMPLE
    .\scripts\render_trailer.ps1
    .\scripts\render_trailer.ps1 -SkipConcat
    .\scripts\render_trailer.ps1 -SkipCards
#>

param(
    [switch]$SkipConcat,
    [switch]$SkipCards,
    [switch]$SkipTerminal
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$outDir = Join-Path $root "demos\trailer"
$clipsDir = Join-Path $outDir "clips"
$python = Join-Path $root ".venv\Scripts\python.exe"

# ── Preflight ──────────────────────────────────────────────────────────────

function Assert-Tool([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "$Name not found in PATH. Install it first."
        exit 1
    }
}

Assert-Tool "ffmpeg"

if (-not (Test-Path $python)) {
    Write-Error ".venv not found at $python"
    exit 1
}

New-Item -ItemType Directory -Path $clipsDir -Force | Out-Null

# ── Render terminal scenes (Pillow) ────────────────────────────────────────

if (-not $SkipTerminal) {
    Write-Host "`n=== Terminal Scenes (Pillow + ffmpeg) ===" -ForegroundColor Cyan
    & $python (Join-Path $root "scripts\make_trailer_terminal.py") --output-dir $clipsDir
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Terminal scene generation failed (exit $LASTEXITCODE)"
    }
}

# ── Render text-card scenes ───────────────────────────────────────────────

if (-not $SkipCards) {
    Write-Host "`n=== Text Cards (Pillow + ffmpeg) ===" -ForegroundColor Cyan
    & $python (Join-Path $root "scripts\make_trailer_cards.py") --output-dir $clipsDir
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Text card generation failed (exit $LASTEXITCODE)"
    }
}

# ── Concatenate all clips ─────────────────────────────────────────────────

if (-not $SkipConcat) {
    Write-Host "`n=== Concatenating final trailer ===" -ForegroundColor Cyan

    # Ordered scene list (must match trailer script scene order)
    $sceneOrder = @(
        "scene01_pytest",
        "scene02_tools",
        "scene03_diff",
        "scene04_statement",
        "scene05_analyze",
        "scene06_phantom",
        "scene07_clonedrift",
        "scene08_boundary",
        "scene09_brief",
        "scene10_nudge",
        "scene11_facts",
        "scene12_tagline",
        "scene13_url"
    )

    # Check all clips exist
    $missing = @()
    foreach ($name in $sceneOrder) {
        $clip = Join-Path $clipsDir "$name.mp4"
        if (-not (Test-Path $clip)) {
            $missing += $name
        }
    }

    if ($missing.Count -gt 0) {
        Write-Warning "Missing clips: $($missing -join ', ')"
        Write-Warning "Run without -SkipTerminal/-SkipCards to generate all clips first."
    } else {
        # Build concat file
        $concatPath = Join-Path $outDir "concat.txt"
        $concatLines = $sceneOrder | ForEach-Object { "file 'clips/$_.mp4'" }
        Set-Content -Path $concatPath -Value ($concatLines -join "`n") -Encoding UTF8

        # First pass: re-encode all clips to uniform format
        $normDir = Join-Path $outDir "_normalized"
        New-Item -ItemType Directory -Path $normDir -Force | Out-Null

        foreach ($name in $sceneOrder) {
            $src = Join-Path $clipsDir "$name.mp4"
            $dst = Join-Path $normDir "$name.mp4"
            ffmpeg -y -i $src `
                -c:v libx264 -preset medium -crf 18 `
                -r 30 `
                -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black" `
                -pix_fmt yuv420p `
                -an `
                $dst 2>&1 | Out-Null
        }

        # Build normalized concat file
        $normConcatPath = Join-Path $outDir "concat_norm.txt"
        $normConcatLines = $sceneOrder | ForEach-Object { "file '_normalized/$_.mp4'" }
        Set-Content -Path $normConcatPath -Value ($normConcatLines -join "`n") -Encoding UTF8

        $finalMp4 = Join-Path $outDir "trailer_all_green_all_wrong.mp4"
        Push-Location $outDir
        ffmpeg -y -f concat -safe 0 -i "concat_norm.txt" -c copy $finalMp4 2>&1 | Out-Null
        Pop-Location

        if (Test-Path $finalMp4) {
            $size = (Get-Item $finalMp4).Length / 1MB
            Write-Host "`n  DONE: $finalMp4" -ForegroundColor Green
            Write-Host "  Size: $([math]::Round($size, 1)) MB"
        } else {
            Write-Warning "Final trailer was not created."
        }
    }
}

Write-Host "`nTrailer pipeline complete." -ForegroundColor Cyan
