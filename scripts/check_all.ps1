param()

if (-not $env:DATABASE_URL) {
    Write-Error "DATABASE_URL is not set. See backend/docs/postgres-migration.md for setup." -ErrorAction Stop
}

Push-Location "$PSScriptRoot/../backend"

function Invoke-Poetry {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$PoetryArgs
    )

    $poetryCmd = Get-Command poetry -ErrorAction SilentlyContinue
    if ($poetryCmd) {
        & $poetryCmd.Path @PoetryArgs
    }
    else {
        & py -m poetry @PoetryArgs
    }
}

function Invoke-Newman {
    param(
        [string]$Collection,
        [string]$Environment
    )

    if ($env:SKIP_NEWMAN) {
        Write-Host "SKIP_NEWMAN set; skipping newman smoke tests."
        return
    }

    $newmanCmd = Get-Command newman -ErrorAction SilentlyContinue
    $useNpx = $false
    $runner = $newmanCmd?.Path

    if (-not $runner) {
        $npxCmd = Get-Command npx -ErrorAction SilentlyContinue
        if (-not $npxCmd) {
            throw "newman not found and npx unavailable. Install Node.js/newman or set SKIP_NEWMAN=1 to skip smoke tests."
        }
        $runner = $npxCmd.Path
        $useNpx = $true
    }

    $args = @("run", $Collection)
    if ($Environment) {
        $args += @("-e", $Environment)
    }
    $args += @("--timeout-request", "20000", "--delay-request", "50", "--color", "on")

    if ($useNpx) {
        & $runner --yes newman @args
    }
    else {
        & $runner @args
    }
}

try {
    Invoke-Poetry install --no-interaction --no-root
    Invoke-Poetry run ruff check .
    Invoke-Poetry run mypy .
    Invoke-Poetry run bandit -q -r app
    Invoke-Poetry run pip-audit --strict
    Invoke-Poetry run pytest --cov=app --cov-report=term --cov-report=xml --cov-fail-under=80
    $collectionPath = $env:POSTMAN_COLLECTION_PATH
    if (-not $collectionPath) { $collectionPath = "postman-smoke-collection.json" }
    $environmentPath = $env:POSTMAN_ENV_PATH
    if (-not $environmentPath) { $environmentPath = "postman-env.local.json" }
    if (Test-Path $collectionPath) {
        if (-not (Test-Path $environmentPath)) {
            Write-Warning "Postman environment file '$environmentPath' not found; running without environment overrides."
            $environmentPath = $null
        }
        Invoke-Newman -Collection $collectionPath -Environment $environmentPath
    }
    else {
        Write-Warning "Postman collection '$collectionPath' not found; skipping smoke API run."
    }
    $alembicPath = Join-Path $env:TEMP "alembic.sql"
    Invoke-Poetry run alembic upgrade head --sql | Out-File -FilePath $alembicPath -Encoding ascii
    Write-Host "All checks completed. Alembic SQL written to $alembicPath"
}
finally {
    Pop-Location
}
