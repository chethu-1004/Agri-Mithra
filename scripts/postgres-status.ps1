. (Join-Path $PSScriptRoot 'postgres-common.ps1')

$config = Get-AgriDatabaseConfig
$services = @(Get-AgriPostgresServices)
$pgIsReady = Get-AgriPostgresTool -Name 'pg_isready' -Services $services

Write-Host 'AgriNetra PostgreSQL status'
Write-Host ("App configuration: {0}:{1} / database {2} / role {3}" -f $config.Host, $config.Port, $config.Database, $config.Username)
if ($services.Count -eq 0) {
    Write-Host 'PostgreSQL Windows services: none detected.'
} else {
    Write-Host 'PostgreSQL Windows services:'
    foreach ($service in $services) {
        $portText = if ($service.Port) { [string]$service.Port } else { 'not found in service postgresql.conf' }
        Write-Host ("  {0} | {1} | startup {2} | port {3}" -f $service.Name, $service.State, $service.StartMode, $portText)
        if ($service.Port) {
            if ($pgIsReady) {
                & $pgIsReady -q -h '127.0.0.1' -p $service.Port
                if ($LASTEXITCODE -eq 0) { Write-Host '    PostgreSQL accepts connections on this port.' }
                else { Write-Host '    PostgreSQL is not accepting connections on this port.' }
            } elseif (Test-AgriTcpPort -HostName '127.0.0.1' -Port $service.Port) {
                Write-Host '    TCP listener detected; pg_isready.exe was not found.'
            } else {
                Write-Host '    No TCP listener detected on this port.'
            }
        }
    }
}

if ($pgIsReady) {
    & $pgIsReady -q -h $config.Host -p $config.Port -d $config.Database -U $config.Username
    if ($LASTEXITCODE -eq 0) { Write-Host 'Configured app endpoint: PostgreSQL server is reachable (authentication is not verified).' }
    else { Write-Host 'Configured app endpoint: PostgreSQL is not accepting connections.' }
} elseif (Test-AgriTcpPort -HostName $config.Host -Port $config.Port) {
    Write-Host 'Configured app endpoint: TCP listener detected; pg_isready.exe was not found.'
} else {
    Write-Host 'Configured app endpoint: no TCP listener detected.'
}

$psql = Get-AgriPostgresTool -Name 'psql' -Services $services
if ($psql) { Write-Host ("psql: {0}" -f $psql) } else { Write-Host 'psql: not found in PATH or detected PostgreSQL installation folders.' }
