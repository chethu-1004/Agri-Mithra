param(
    [switch]$BackupVerified,
    [string]$HostName = '127.0.0.1',
    [int]$Port = 0,
    [string]$Username = 'agrinetra',
    [string]$Database = 'agrinetra_import'
)

. (Join-Path $PSScriptRoot 'postgres-common.ps1')

if (-not $BackupVerified) {
    throw 'This updates the backend .env database target. First create and verify a Docker database backup and restore it into a separate native database, then rerun with -BackupVerified.'
}
if ([string]::IsNullOrWhiteSpace($Username) -or [string]::IsNullOrWhiteSpace($Database)) {
    throw 'Username and database must not be empty.'
}
if ($Port -eq 0) {
    $services = @(Get-AgriPostgresServices | Where-Object { $_.Port })
    if ($services.Count -ne 1) {
        throw 'Could not choose a native PostgreSQL service port unambiguously. Supply its verified port using -Port.'
    }
    $Port = [int]$services[0].Port
}
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Port must be between 1 and 65535.' }
if (-not (Test-AgriTcpPort -HostName $HostName -Port $Port)) {
    throw ("No PostgreSQL listener is available at {0}:{1}. Start the native service and verify its port first." -f $HostName, $Port)
}

$envPath = Join-Path $script:AgriBackendRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Existing backend .env was not found at $envPath. Create it from .env.example and preserve your other settings before changing the database URL."
}
$contents = [System.IO.File]::ReadAllText($envPath)
$urlMatches = [regex]::Matches($contents, '(?m)^[ \t]*DATABASE_URL[ \t]*=')
if ($urlMatches.Count -gt 1) { throw 'The existing .env has more than one DATABASE_URL entry. Resolve the duplicate manually before updating it.' }

$securePassword = Read-Host 'Native PostgreSQL application-role password' -AsSecureString
$passwordPointer = [IntPtr]::Zero
$plainPassword = $null
$temporaryPath = $null
try {
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if ([string]::IsNullOrEmpty($plainPassword)) { throw 'The password cannot be empty.' }

    $encodedUser = [Uri]::EscapeDataString($Username)
    $encodedPassword = [Uri]::EscapeDataString($plainPassword)
    $encodedDatabase = [Uri]::EscapeDataString($Database)
    $newUrl = "postgresql+psycopg://${encodedUser}:${encodedPassword}@${HostName}:${Port}/${encodedDatabase}"
    $pattern = '(?m)^[ \t]*DATABASE_URL[ \t]*=[^\r\n]*'
    $regex = [regex]::new($pattern)
    if ($urlMatches.Count -eq 1) {
        $replacement = [System.Text.RegularExpressions.MatchEvaluator]{ param($match) "DATABASE_URL=$newUrl" }
        $updated = $regex.Replace($contents, $replacement, 1)
    } else {
        $newline = if ($contents.Contains("`r`n")) { "`r`n" } else { "`n" }
        $separator = if ($contents.Length -eq 0 -or $contents.EndsWith("`n")) { '' } else { $newline }
        $updated = $contents + $separator + "DATABASE_URL=$newUrl" + $(if ($separator -or $contents.EndsWith("`n")) { $newline } else { '' })
    }

    $temporaryPath = Join-Path (Split-Path -Parent $envPath) ('.env.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    [System.IO.File]::WriteAllText($temporaryPath, $updated, [System.Text.UTF8Encoding]::new($false))
    Set-Acl -LiteralPath $temporaryPath -AclObject (Get-Acl -LiteralPath $envPath)
    [System.IO.File]::Replace($temporaryPath, $envPath, $null)
    $temporaryPath = $null
    Write-Host ("Updated DATABASE_URL in {0}; all other .env entries were preserved. The URL/password was not printed." -f $envPath)
} finally {
    if ($temporaryPath -and (Test-Path -LiteralPath $temporaryPath)) { Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue }
    if ($passwordPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }
    $plainPassword = $null
    if ($securePassword) { $securePassword.Dispose() }
}
