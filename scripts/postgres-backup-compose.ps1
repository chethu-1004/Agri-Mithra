param(
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'backend\backups')
)

$composeDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'backend\backend'
$docker = Get-Command docker.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $docker) { throw 'docker.exe was not found. Start Docker Desktop temporarily to export the existing database.' }

$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $OutputDirectory "agrinetra-docker-$stamp.dump"
$tempPath = "$backupPath.partial"

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $docker.Source
$startInfo.Arguments = 'compose exec -T postgres pg_dump -Fc -U agrinetra -d agrinetra'
$startInfo.WorkingDirectory = $composeDirectory
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $startInfo
try {
    if (-not $process.Start()) { throw 'Could not start Docker Compose.' }
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $file = [System.IO.File]::Create($tempPath)
    try { $process.StandardOutput.BaseStream.CopyTo($file) } finally { $file.Dispose() }
    $process.WaitForExit()
    $null = $stderrTask.GetAwaiter().GetResult()
    if ($process.ExitCode -ne 0) {
        Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
        throw ("Docker pg_dump failed with exit code {0}. Confirm Docker Desktop is running and the Compose postgres service is healthy; no backup was marked verified." -f $process.ExitCode)
    }
} finally {
    $process.Dispose()
}

if (-not (Test-Path -LiteralPath $tempPath) -or (Get-Item -LiteralPath $tempPath).Length -lt 5) {
    Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
    throw 'pg_dump returned success but produced no usable archive; the backup was not verified.'
}
Move-Item -LiteralPath $tempPath -Destination $backupPath

$services = @(Get-CimInstance -ClassName Win32_Service -Filter "Name LIKE 'postgresql%'" -ErrorAction SilentlyContinue | ForEach-Object {
    $binaryDirectory = $null
    if ($_.PathName -match '^(?:"(?<exe>[^"]+)"|(?<exe>.*?postgres\.exe))') { $binaryDirectory = Split-Path -Parent $Matches['exe'] }
    [pscustomobject]@{ BinaryDirectory = $binaryDirectory }
})
$pgRestore = $null
if (Get-Command pg_restore.exe -ErrorAction SilentlyContinue) { $pgRestore = (Get-Command pg_restore.exe).Source }
if (-not $pgRestore) {
    foreach ($service in $services) {
        if ($service.BinaryDirectory) {
            $candidate = Join-Path $service.BinaryDirectory 'pg_restore.exe'
            if (Test-Path -LiteralPath $candidate) { $pgRestore = $candidate; break }
        }
    }
}
if (-not $pgRestore) {
    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $root) { continue }
        $pgRoot = Join-Path $root 'PostgreSQL'
        if (Test-Path -LiteralPath $pgRoot) {
            $candidate = Get-ChildItem -LiteralPath $pgRoot -Filter pg_restore.exe -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($candidate) { $pgRestore = $candidate.FullName; break }
        }
    }
}
if (-not $pgRestore) {
    throw ("Backup archive exists but could not be verified because pg_restore.exe was not found: {0}" -f $backupPath)
}
& $pgRestore --list $backupPath *> $null
if ($LASTEXITCODE -ne 0) { throw ("Backup file exists but pg_restore could not read its archive. Keep it for investigation; it is not verified: {0}" -f $backupPath) }

$hash = (Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash
Write-Host ("Verified PostgreSQL custom-format archive: {0}" -f $backupPath)
Write-Host ("Size: {0} bytes" -f (Get-Item -LiteralPath $backupPath).Length)
Write-Host ("SHA-256: {0}" -f $hash)
Write-Host 'The Docker database and volume were not modified.'
