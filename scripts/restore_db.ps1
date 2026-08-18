# Restore contractlens_backup.dump into the running postgres service.
# Place dump at repo root, then:
#   powershell -File scripts/restore_db.ps1
#
# Dump is copied into the container (compose no longer bind-mounts /backup).

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$user = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "contractlens" }
$db = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "contractlens" }
$hostDump = Join-Path (Get-Location) "contractlens_backup.dump"
$containerDump = "/tmp/contractlens_backup.dump"

if (-not (Test-Path -LiteralPath $hostDump -PathType Leaf)) {
    throw "Missing dump file at repo root: $hostDump"
}

Write-Host "Copying dump into postgres container..."
docker compose cp $hostDump "postgres:$containerDump"

Write-Host "Terminating connections to $db..."
docker compose exec -T postgres psql -U $user -d postgres -v ON_ERROR_STOP=1 `
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid();"

Write-Host "Recreating database $db..."
docker compose exec -T postgres psql -U $user -d postgres -v ON_ERROR_STOP=1 `
  -c "DROP DATABASE IF EXISTS $db;" `
  -c "CREATE DATABASE $db OWNER $user;"

Write-Host "Restoring $containerDump (multi-GB dump may take a long time)..."
docker compose exec -T postgres pg_restore `
  -U $user `
  -d $db `
  --no-owner `
  --no-acl `
  --verbose `
  $containerDump

Write-Host "Done. Tables:"
docker compose exec -T postgres psql -U $user -d $db -c "\dt"
