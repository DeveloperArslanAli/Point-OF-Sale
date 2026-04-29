param(
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot/../backend"
try {
    if (-not (Test-Path ".env.local")) {
        Write-Warning ".env.local not found; falling back to defaults/.env"
    }

    if ($NoReload.IsPresent) {
        $reloadFlag = ""
    } else {
        $reloadFlag = " --reload"
    }

    $cmd = "py -m poetry run uvicorn app.api.main:app --port $Port$reloadFlag"

    Write-Host "Starting API on port $Port" -ForegroundColor Cyan
    Write-Host "Command: $cmd" -ForegroundColor DarkGray

    # Run in the foreground so logs remain attached to the invoking terminal.
    Invoke-Expression $cmd
}
finally {
    Pop-Location
}
