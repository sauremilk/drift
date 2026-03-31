param(
    [string]$Repo = "sauremilk/drift"
)

$ErrorActionPreference = "Stop"

$labels = @(
    @{ Name = "priority: high"; Color = "b60205"; Description = "Credibility, signal precision, or finding clarity" },
    @{ Name = "priority: medium"; Color = "d93f0b"; Description = "FP/FN reduction or adoptability improvements" },
    @{ Name = "priority: low"; Color = "fbca04"; Description = "Comfort features, cosmetic docs, or trend improvements" },
    @{ Name = "size: small"; Color = "0e8a16"; Description = "Less than 50 changed lines - quick review" },
    @{ Name = "size: medium"; Color = "1d76db"; Description = "50-200 changed lines" },
    @{ Name = "size: large"; Color = "5319e7"; Description = "More than 200 changed lines - needs dedicated review slot" },
    @{ Name = "needs: rebase"; Color = "e99695"; Description = "Merge conflicts - contributor must rebase on master" },
    @{ Name = "needs: tests"; Color = "e99695"; Description = "Test coverage missing or incomplete" },
    @{ Name = "needs: evidence"; Color = "e99695"; Description = "Feature evidence artifact required (see PR template)" },
    @{ Name = "needs: changes"; Color = "e99695"; Description = "Reviewer requested changes" },
    @{ Name = "false-positive"; Color = "d93f0b"; Description = "Drift flags something that is not a real issue" },
    @{ Name = "false-negative"; Color = "d93f0b"; Description = "Drift misses something that is a real issue" },
    @{ Name = "signal-quality"; Color = "0075ca"; Description = "Improves precision, recall, or explainability of a signal" },
    @{ Name = "needs reproduction"; Color = "fbca04"; Description = "A minimal reproducing case is needed before work can start" },
    @{ Name = "not-prioritized"; Color = "e4e4e4"; Description = "Acknowledged but not currently prioritized" },
    @{ Name = "stale"; Color = "ededed"; Description = "Inactive for 90+ days - will auto-close if no further activity" },
    @{ Name = "docs"; Color = "c5def5"; Description = "Documentation improvements" },
    @{ Name = "tests"; Color = "bfd4f2"; Description = "Test coverage or fixture improvements" }
)

Write-Host "Setting up labels on $Repo ..."
Write-Host "Authenticated account:"
gh auth status | Select-String "Active account" | ForEach-Object { Write-Host "  $($_.Line.Trim())" }

$existing = @()
try {
    $existing = gh label list --repo $Repo --limit 200 --json name --jq '.[].name'
} catch {
    Write-Error "Failed to list existing labels. Check gh authentication."
    exit 1
}

$created = 0
$skipped = 0
$failed = 0

foreach ($label in $labels) {
    if ($existing -contains $label.Name) {
        Write-Host "SKIP (exists): $($label.Name)"
        $skipped++
        continue
    }

    try {
        $output = gh label create $label.Name --repo $Repo --color $label.Color --description $label.Description 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "CREATED: $($label.Name)"
            $created++
        } else {
            Write-Host "FAILED: $($label.Name)"
            if ($output) {
                Write-Host "  $output"
            }
            $failed++
        }
    } catch {
        Write-Host "FAILED: $($label.Name)"
        Write-Host "  $($_.Exception.Message)"
        $failed++
    }
}

Write-Host ""
Write-Host "Done: $created created, $skipped skipped, $failed failed."

if ($failed -gt 0) {
    Write-Host ""
    Write-Host "One or more label operations failed."
    Write-Host "If you use two accounts, authenticate gh as mick-gsk and run this script again:"
    Write-Host "  gh auth login"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/setup_github_labels.ps1 -Repo $Repo"
    exit 1
}
