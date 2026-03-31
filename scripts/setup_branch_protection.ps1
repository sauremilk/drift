param(
    [string]$Owner = "sauremilk",
    [string]$Repo = "drift",
    [string]$Branch = "master"
)

$ErrorActionPreference = "Stop"

$checks = @(
    @{ context = "Version format check" },
    @{ context = "Test (Python 3.12)" },
    @{ context = "Blocked content check" },
    @{ context = "Auto-label by path" },
    @{ context = "Size label" }
)

$payload = @{
    required_status_checks = @{
        strict = $true
        contexts = $checks.context
    }
    enforce_admins = $true
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $true
        require_code_owner_reviews = $false
        required_approving_review_count = 1
    }
    restrictions = $null
    required_linear_history = $false
    allow_force_pushes = $false
    allow_deletions = $false
    block_creations = $false
    required_conversation_resolution = $true
    lock_branch = $false
    allow_fork_syncing = $true
}

$uri = "repos/$Owner/$Repo/branches/$Branch/protection"
$json = $payload | ConvertTo-Json -Depth 10

Write-Host "Applying branch protection to $Owner/$Repo ($Branch) ..."
Write-Host "Authenticated account:"
gh auth status | Select-String "Active account" | ForEach-Object { Write-Host "  $($_.Line.Trim())" }

$tmp = [System.IO.Path]::GetTempFileName()
try {
    Set-Content -Path $tmp -Value $json -Encoding UTF8
    $result = gh api $uri -X PUT --input $tmp -H "Accept: application/vnd.github+json" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED to apply branch protection"
        Write-Host $result
        exit 1
    }

    Write-Host "Branch protection updated successfully."
    Write-Host "Required checks:"
    foreach ($c in $checks.context) {
        Write-Host "  - $c"
    }
} finally {
    Remove-Item -Path $tmp -ErrorAction SilentlyContinue
}
