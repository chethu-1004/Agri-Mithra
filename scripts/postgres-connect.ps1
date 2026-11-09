. (Join-Path $PSScriptRoot 'postgres-common.ps1')

$config = Get-AgriDatabaseConfig
$services = @(Get-AgriPostgresServices)
$pgIsReady = Get-AgriPostgresTool -Name 'pg_isready' -Services $services
$psql = Get-AgriPostgresTool -Name 'psql' -Services $services
if (-not $psql) { throw 'psql.exe was not found. Install PostgreSQL command-line tools or add the installed PostgreSQL bin folder to PATH.' }
if ($pgIsReady) {
    & $pgIsReady -q -h $config.Host -p $config.Port -d $config.Database -U $config.Username
    if ($LASTEXITCODE -ne 0) { throw ("No PostgreSQL server is accepting connections at {0}:{1}. Run scripts\postgres-status.ps1 and check the configured port." -f $config.Host, $config.Port) }
} elseif (-not (Test-AgriTcpPort -HostName $config.Host -Port $config.Port)) {
    throw ("No PostgreSQL server is accepting connections at {0}:{1}. Run scripts\postgres-status.ps1 and check the configured port." -f $config.Host, $config.Port)
}

Write-Host ("Connecting to database {0} as role {1} at {2}:{3}. Enter the database password at psql's hidden prompt." -f $config.Database, $config.Username, $config.Host, $config.Port)
& $psql -X -W -v ON_ERROR_STOP=1 -h $config.Host -p $config.Port -U $config.Username -d $config.Database -c 'SELECT 1 AS connected;'
if ($LASTEXITCODE -ne 0) { throw 'The connection check failed. Confirm the role, password, database, and port; this script did not change database objects.' }
Write-Host 'AgriNetra PostgreSQL connection verified.'
