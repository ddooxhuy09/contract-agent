# Restore neo4j.dump into the Neo4j Docker volume (offline load).
# Usage (repo root):
#   powershell -File scripts/restore_neo4j.ps1
#
# Neo4j MUST be stopped while loading (neo4j-admin offline). Script starts it again after.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$dumpHost = Join-Path (Get-Location) "neo4j.dump"
if (-not (Test-Path -LiteralPath $dumpHost)) {
    throw "Missing neo4j.dump at repo root: $dumpHost"
}

$project = if ($env:COMPOSE_PROJECT_NAME) { $env:COMPOSE_PROJECT_NAME } else { "contractlens" }
$volume = "${project}_neo4jdata"
$user = if ($env:NEO4J_USER) { $env:NEO4J_USER } else { "neo4j" }
$pass = if ($env:NEO4J_PASSWORD) { $env:NEO4J_PASSWORD } else { "contractlens" }

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [Parameter(Mandatory = $true)][string[]]$CmdArgs
    )
    Write-Host (">> {0} {1}" -f $File, ($CmdArgs -join " ")) -ForegroundColor DarkGray
    & $File @CmdArgs
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed (exit {0}): {1} {2}" -f $LASTEXITCODE, $File, ($CmdArgs -join " "))
    }
}

try {
    Write-Host "1/4 Stopping neo4j (required for offline load)..." -ForegroundColor Cyan
    Invoke-Native -File docker -CmdArgs @("compose", "stop", "neo4j")

    $volName = docker volume ls -q --filter ("name={0}" -f $volume)
    if (-not $volName) {
        Write-Host ("Volume {0} missing - creating via compose..." -f $volume) -ForegroundColor Yellow
        Invoke-Native -File docker -CmdArgs @("compose", "up", "-d", "neo4j")
        Start-Sleep -Seconds 8
        Invoke-Native -File docker -CmdArgs @("compose", "stop", "neo4j")
    }

    Write-Host ("2/4 Loading dump into volume {0} (overwrite)..." -f $volume) -ForegroundColor Cyan
    $dumpMount = "{0}:/backups/neo4j.dump:ro" -f $dumpHost
    $dataMount = "{0}:/data" -f $volume
    Invoke-Native -File docker -CmdArgs @(
        "run", "--rm",
        "-v", $dataMount,
        "-v", $dumpMount,
        "--entrypoint", "neo4j-admin",
        "neo4j:5",
        "database", "load", "neo4j",
        "--from-path=/backups",
        "--overwrite-destination=true"
    )

    Write-Host "3/4 Starting neo4j again..." -ForegroundColor Cyan
    Invoke-Native -File docker -CmdArgs @("compose", "up", "-d", "neo4j")

    Write-Host "4/4 Waiting for healthy..." -ForegroundColor Cyan
    $ok = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 3
        $status = docker compose ps neo4j --format "{{.Status}}" 2>$null
        if ($status -match "healthy") {
            $ok = $true
            break
        }
        Write-Host ("  status: {0}" -f $status)
    }
    if (-not $ok) {
        Write-Warning "Neo4j not healthy yet - check: docker compose ps neo4j / docker compose logs neo4j"
    }

    Write-Host "Node counts:" -ForegroundColor Cyan
    $cypher = "MATCH (n) RETURN labels(n) AS labels, count(*) AS cnt ORDER BY cnt DESC LIMIT 15;"
    docker compose exec -T neo4j cypher-shell -u $user -p $pass $cypher

    Write-Host "Done." -ForegroundColor Green
}
catch {
    Write-Host ("ERROR: {0}" -f $_.Exception.Message) -ForegroundColor Red
    Write-Host "Trying to bring neo4j back up..." -ForegroundColor Yellow
    docker compose up -d neo4j | Out-Null
    throw
}
