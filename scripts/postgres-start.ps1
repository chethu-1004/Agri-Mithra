. (Join-Path $PSScriptRoot 'postgres-common.ps1')

$config = Get-AgriDatabaseConfig
$services = @(Get-AgriPostgresServices)
if ($services.Count -eq 0) { throw 'No PostgreSQL Windows service was detected. Install PostgreSQL with the official Windows installer first.' }

$matching = @($services | Where-Object { $_.Port -eq $config.Port })
if ($matching.Count -eq 1) {
    $service = $matching[0]
} elseif ($services.Count -eq 1) {
    $service = $services[0]
} else {
    throw ("Found {0} PostgreSQL services and cannot identify one safely. The configured app port is {1}; specify a matching service by correcting its port configuration, then retry." -f $services.Count, $config.Port)
}
if (-not $service.Port) { throw ("Could not read the listening port from {0}'s postgresql.conf; refusing to start an unidentified instance." -f $service.Name) }

if ($service.State -eq 'Running') {
    Write-Host ("PostgreSQL service {0} is already running on configured service port {1}." -f $service.Name, $service.Port)
    exit 0
}

if (Test-AgriTcpPort -HostName '127.0.0.1' -Port $service.Port) {
    throw ("Port {0} already has a listener while service {1} is stopped. Refusing to start a possible duplicate instance." -f $service.Port, $service.Name)
}

try {
    Start-Service -Name $service.Name -ErrorAction Stop
} catch {
    throw ("Could not start {0}. If Windows reports access denied, open an elevated PowerShell terminal and run this task again. No startup mode was changed. Details: {1}" -f $service.Name, $_.Exception.Message)
}

$pgIsReady = Get-AgriPostgresTool -Name 'pg_isready' -Services $services
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    if ($pgIsReady) {
        & $pgIsReady -q -h '127.0.0.1' -p $service.Port
        if ($LASTEXITCODE -eq 0) {
            Write-Host ("PostgreSQL service {0} is ready on port {1}." -f $service.Name, $service.Port)
            exit 0
        }
    } elseif (Test-AgriTcpPort -HostName '127.0.0.1' -Port $service.Port) {
        Write-Host ("PostgreSQL service {0} is listening on port {1}; pg_isready.exe was not found." -f $service.Name, $service.Port)
        exit 0
    }
}
throw ("Service {0} started but PostgreSQL did not become available on port {1} within 30 seconds. Check Windows Event Viewer and the PostgreSQL server log." -f $service.Name, $service.Port)
