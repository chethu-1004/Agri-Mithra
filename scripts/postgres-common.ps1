Set-StrictMode -Version Latest

$script:AgriProjectRoot = Split-Path -Parent $PSScriptRoot
$script:AgriBackendRoot = Join-Path $script:AgriProjectRoot 'backend\backend'

function Get-AgriDatabaseConfig {
    $databaseUrl = $env:DATABASE_URL
    if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
        $envPath = Join-Path $script:AgriBackendRoot '.env'
        if (-not (Test-Path -LiteralPath $envPath)) {
            $envPath = Join-Path $script:AgriBackendRoot '.env.example'
        }
        if (-not (Test-Path -LiteralPath $envPath)) {
            throw 'No backend .env or .env.example was found.'
        }

        $line = Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
        if ($null -eq $line) { throw "DATABASE_URL is missing from $envPath." }
        $databaseUrl = ($line -replace '^\s*DATABASE_URL\s*=\s*', '').Trim()
        if (($databaseUrl.StartsWith('"') -and $databaseUrl.EndsWith('"')) -or
            ($databaseUrl.StartsWith("'") -and $databaseUrl.EndsWith("'"))) {
            $databaseUrl = $databaseUrl.Substring(1, $databaseUrl.Length - 2)
        }
    }

    try { $uri = [Uri]$databaseUrl } catch { throw 'DATABASE_URL is not a valid PostgreSQL URL. Check its format without sharing its password.' }
    if ($uri.Scheme -notlike 'postgresql*' -or [string]::IsNullOrWhiteSpace($uri.Host)) {
        throw 'DATABASE_URL must be a PostgreSQL SQLAlchemy URL with a host.'
    }
    $userInfo = $uri.UserInfo -split ':', 2
    if ($userInfo.Count -lt 1 -or [string]::IsNullOrWhiteSpace($userInfo[0])) {
        throw 'DATABASE_URL must include the configured database username.'
    }
    $database = [Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart('/'))
    if ([string]::IsNullOrWhiteSpace($database)) { throw 'DATABASE_URL must include the database name.' }

    $port = $uri.Port
    if ($port -lt 1) { $port = 5432 }
    return [pscustomobject]@{
        Host = $uri.Host
        Port = $port
        Username = [Uri]::UnescapeDataString($userInfo[0])
        Database = $database
    }
}

function Get-AgriPostgresServices {
    try {
        $services = @(Get-CimInstance -ClassName Win32_Service -Filter "Name LIKE 'postgresql%'" -ErrorAction Stop)
    } catch {
        throw 'Could not inspect Windows services. Run this script in Windows PowerShell or PowerShell with permission to query services.'
    }

    foreach ($service in $services) {
        $dataDirectory = $null
        $port = $null
        $binaryPath = [string]$service.PathName
        if ($binaryPath -match '(?i)\s-D\s+"(?<data>[^"]+)"') {
            $dataDirectory = $Matches['data']
        } elseif ($binaryPath -match '(?i)\s-D\s+(?<data>\S+)') {
            $dataDirectory = $Matches['data']
        }
        if ($dataDirectory) {
            $configPath = Join-Path $dataDirectory 'postgresql.conf'
            if (Test-Path -LiteralPath $configPath) {
                foreach ($configLine in Get-Content -LiteralPath $configPath) {
                    if ($configLine -match '^\s*port\s*=\s*''?(?<port>\d+)''?(?:\s|#|$)') {
                        $port = [int]$Matches['port']
                    }
                }
            }
        }

        $exeDirectory = $null
        if ($binaryPath -match '^(?:"(?<exe>[^"]+)"|(?<exe>.*?postgres\.exe))') {
            $exeDirectory = Split-Path -Parent $Matches['exe']
        }
        [pscustomobject]@{
            Name = [string]$service.Name
            DisplayName = [string]$service.DisplayName
            State = [string]$service.State
            StartMode = [string]$service.StartMode
            DataDirectory = $dataDirectory
            Port = $port
            BinaryDirectory = $exeDirectory
        }
    }
}

function Get-AgriPostgresTool {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [object[]]$Services = @()
    )

    $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }

    $candidateDirectories = @()
    foreach ($service in $Services) {
        if ($service.BinaryDirectory) { $candidateDirectories += $service.BinaryDirectory }
    }
    foreach ($programFiles in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ([string]::IsNullOrWhiteSpace($programFiles)) { continue }
        $root = Join-Path $programFiles 'PostgreSQL'
        if (Test-Path -LiteralPath $root) {
            foreach ($version in Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue) {
                $candidateDirectories += Join-Path $version.FullName 'bin'
            }
        }
    }
    foreach ($directory in ($candidateDirectories | Select-Object -Unique)) {
        $candidate = Join-Path $directory "$Name.exe"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

function Test-AgriTcpPort {
    param([Parameter(Mandatory = $true)][string]$HostName, [Parameter(Mandatory = $true)][int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $result = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne(1500, $false)) { return $false }
        $client.EndConnect($result)
        return $true
    } catch { return $false } finally { $client.Dispose() }
}
