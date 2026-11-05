# One-time Windows setup for the Student Result Management System. Started by setup.bat; safe to run again.
$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root '.venv'
$VenvPy = Join-Path $Venv 'Scripts\python.exe'
$Helper = Join-Path $PSScriptRoot 'setup_helper.py'
$MySqlPort = 3306
$script:FreshMySql = $false

function Write-Step($text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text) { Write-Host "    $text" -ForegroundColor Green }
function Write-Note($text) { Write-Host "    $text" -ForegroundColor Yellow }

function Stop-Setup($text) {
    Write-Host ''
    Write-Host "Setup stopped: $text" -ForegroundColor Red
    Write-Host 'Fix the problem above, then double-click setup.bat again. It is safe to run it more than once.'
    Read-Host 'Press Enter to close'
    exit 1
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Update-SessionPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-WingetPackage($id, $name, $scope) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        Stop-Setup "$name is not installed and winget is missing. Install 'App Installer' from the Microsoft Store (or install $name by hand, see README), then run setup.bat again."
    }
    Write-Host "    Downloading and installing $name. This can take a few minutes..."
    $wingetArgs = @('install', '--exact', '--id', $id, '--source', 'winget', '--silent', '--accept-package-agreements', '--accept-source-agreements')
    if ($scope) { $wingetArgs += @('--scope', $scope) }
    & winget.exe @wingetArgs
    if ($LASTEXITCODE -ne 0) { Write-Note "winget finished with code $LASTEXITCODE. Checking whether $name is usable anyway..." }
}

function Test-PythonOk($exe) {
    if (-not $exe -or -not (Test-Path -LiteralPath $exe)) { return $false }
    if ($exe -like '*\WindowsApps\*') { return $false }
    & $exe -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Find-Python {
    $candidates = New-Object System.Collections.Generic.List[string]
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $found = & $launcher.Path -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $found) { $candidates.Add(([string]$found).Trim()) }
    }
    foreach ($command in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)) { $candidates.Add($command.Path) }
    foreach ($pattern in @("$env:ProgramFiles\Python3*\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe")) {
        Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue |
            Sort-Object { [int]($_.Directory.Name -replace '[^0-9]', '') } -Descending |
            ForEach-Object { $candidates.Add($_.FullName) }
    }
    foreach ($candidate in $candidates) {
        if (Test-PythonOk $candidate) { return $candidate }
    }
    return $null
}

function Invoke-Helper([string[]]$HelperArgs) {
    $global:LASTEXITCODE = 1
    & $VenvPy $Helper @HelperArgs | Out-Host
    return $LASTEXITCODE
}

function Test-Port($port) {
    $client = New-Object Net.Sockets.TcpClient
    try { $client.Connect('127.0.0.1', $port); return $true } catch { return $false } finally { $client.Close() }
}

function Wait-Port($port, $seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Read-Secret($prompt) {
    $secure = Read-Host -Prompt $prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Find-Mysqld {
    $found = Get-ChildItem -Path "$env:ProgramFiles\MySQL\MySQL Server *\bin\mysqld.exe" -ErrorAction SilentlyContinue |
        Sort-Object { $_.Directory.Parent.Name } -Descending |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Start-MySqlServices {
    $services = @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'mysql*' })
    foreach ($service in $services) {
        if ($service.Status -eq 'Running' -or $service.StartType -eq 'Disabled') { continue }
        Write-Host "    Starting the $($service.Name) service..."
        try {
            if ($service.StartType -eq 'Manual') { Set-Service -Name $service.Name -StartupType Automatic -ErrorAction Stop }
            Start-Service -Name $service.Name -ErrorAction Stop
        } catch {
            Write-Note "Could not start $($service.Name): $($_.Exception.Message)"
        }
    }
    if ($services.Count -gt 0) { Wait-Port $MySqlPort 20 | Out-Null }
}

function Install-MySqlServer {
    $mysqld = Find-Mysqld
    if (-not $mysqld) {
        Install-WingetPackage 'Microsoft.VCRedist.2015+.x64' 'Microsoft Visual C++ Runtime' $null
        Install-WingetPackage 'Oracle.MySQL' 'MySQL Server' $null
        $mysqld = Find-Mysqld
        if (-not $mysqld) { Stop-Setup 'MySQL Server was not found after installing it. Restart the computer and run setup.bat again.' }
    }

    $baseDir = Split-Path -Parent (Split-Path -Parent $mysqld)
    $folder = Split-Path -Leaf $baseDir
    $serviceName = 'MySQL' + ($folder -replace '[^0-9]', '')
    $dataRoot = Join-Path $env:ProgramData "MySQL\$folder"
    $dataDir = Join-Path $dataRoot 'Data'
    $ini = Join-Path $dataRoot 'my.ini'

    if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
        Stop-Setup "The $serviceName service is installed but MySQL is not answering on port $MySqlPort. Open the Services app, start $serviceName, and run setup.bat again."
    }

    New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
    if (-not (Test-Path -LiteralPath $ini)) {
        $lines = @(
            '[mysqld]',
            "basedir=$($baseDir -replace '\\', '/')",
            "datadir=$($dataDir -replace '\\', '/')",
            "port=$MySqlPort",
            'bind-address=127.0.0.1',
            'mysqlx-bind-address=127.0.0.1'
        )
        [IO.File]::WriteAllText($ini, ($lines -join "`r`n") + "`r`n", (New-Object Text.ASCIIEncoding))
    }

    if (-not (Test-Path -LiteralPath (Join-Path $dataDir 'mysql.ibd'))) {
        if (Test-Path -LiteralPath $dataDir) { Remove-Item -LiteralPath $dataDir -Recurse -Force -ErrorAction SilentlyContinue }
        Write-Host '    Preparing the MySQL data folder...'
        & $mysqld "--defaults-file=$ini" --initialize-insecure --console
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -LiteralPath $dataDir -Recurse -Force -ErrorAction SilentlyContinue
            Stop-Setup 'MySQL could not prepare its data folder (see the messages above).'
        }
        $script:FreshMySql = $true
    }

    Write-Host "    Registering the $serviceName Windows service..."
    & $mysqld --install $serviceName "--defaults-file=$ini"
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Could not register the $serviceName Windows service." }
    try { Start-Service -Name $serviceName -ErrorAction Stop } catch { Write-Note $_.Exception.Message }
    if (-not (Wait-Port $MySqlPort 30)) { Stop-Setup "MySQL was installed but did not start. Check the $serviceName service in the Services app." }
}

if (-not (Test-Admin)) {
    Write-Host 'Asking for administrator permission (needed to install Python and MySQL)...'
    try {
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ErrorAction Stop `
            -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    } catch {
        Write-Host 'Administrator permission was not given, so setup cannot continue.' -ForegroundColor Red
        Read-Host 'Press Enter to close'
        exit 1
    }
    exit 0
}

Set-Location -LiteralPath $Root
if ($Root -like '*\OneDrive*') {
    Write-Note 'This folder is inside OneDrive. If setup fails with "Access is denied", move the folder to C:\srms and run setup.bat again.'
}
$Host.UI.RawUI.WindowTitle = 'Student Result Management System - Setup'
Write-Host 'Student Result Management System - Windows setup' -ForegroundColor Cyan
Write-Host "Folder: $Root"

Write-Step 'Step 1 of 5: Python'
$Python = Find-Python
if (-not $Python) {
    Install-WingetPackage 'Python.Python.3.12' 'Python 3.12' 'machine'
    Update-SessionPath
    $Python = Find-Python
    if (-not $Python) { Stop-Setup 'Python was not found after installing it. Restart the computer and run setup.bat again.' }
}
Write-Ok "Using $Python"

Write-Step 'Step 2 of 5: App libraries'
if ((Test-Path -LiteralPath $Venv) -and -not (Test-PythonOk $VenvPy)) {
    Write-Note 'Replacing an old or broken .venv folder (for example one copied from another computer).'
    try { Remove-Item -LiteralPath $Venv -Recurse -Force -ErrorAction Stop }
    catch { Stop-Setup 'Could not delete the old .venv folder. Close the app window (start.bat) and try again.' }
}
if (-not (Test-Path -LiteralPath $VenvPy)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Could not create the .venv folder.' }
}
if (-not (Test-PythonOk $VenvPy)) { Stop-Setup "The .venv folder was created but $VenvPy does not run. An antivirus may be blocking it." }
& $VenvPy -m pip install --disable-pip-version-check -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Stop-Setup 'Installing the Python libraries failed. Check the internet connection.' }
Write-Ok 'Libraries installed.'

Write-Step 'Step 3 of 5: MySQL database server'
if ((Invoke-Helper @('env-ok')) -eq 0) {
    Write-Ok 'MySQL is running and the login saved in .env works.'
} else {
    Start-MySqlServices
    if (-not (Test-Port $MySqlPort)) {
        if (Test-Path -LiteralPath 'C:\xampp\mysql\bin\mysqld.exe') {
            Stop-Setup 'XAMPP is installed but its MySQL is not running. Open the XAMPP Control Panel, click Start next to MySQL, then run setup.bat again.'
        }
        Install-MySqlServer
    }

    $env:SRMS_DB_SECRET = ''
    $global:LASTEXITCODE = 1
    & $VenvPy $Helper check --port "$MySqlPort" | Out-Null
    $rootHasNoPassword = $LASTEXITCODE -eq 0
    $isXampp = Test-Path -LiteralPath 'C:\xampp\mysql'
    if ($script:FreshMySql -or ($rootHasNoPassword -and -not $isXampp)) {
        Write-Host '    Choose a password for the MySQL "root" user and write it down.'
        while ($true) {
            $newPassword = Read-Secret '    New MySQL root password (at least 8 characters)'
            $repeat = Read-Secret '    Type it again'
            if ($newPassword.Length -ge 8 -and $newPassword -ceq $repeat) { break }
            Write-Note 'The passwords were shorter than 8 characters or did not match. Try again.'
        }
        $env:SRMS_DB_SECRET = $newPassword
        if ((Invoke-Helper @('set-root', '--port', "$MySqlPort")) -ne 0) { Stop-Setup 'Could not set the MySQL root password.' }
    } else {
        Write-Host '    MySQL is already installed on this computer. Enter its "root" password.'
        Write-Host '    (If it has no password, for example XAMPP, just press Enter.)'
        $loginOk = $rootHasNoPassword
        if ($loginOk) { Write-Ok 'MySQL root has no password; using that.' }
        for ($attempt = 1; $attempt -le 3 -and -not $loginOk; $attempt++) {
            $env:SRMS_DB_SECRET = Read-Secret '    MySQL root password'
            $status = Invoke-Helper @('check', '--port', "$MySqlPort")
            if ($status -eq 0) { $loginOk = $true }
            elseif ($status -ne 2) { Stop-Setup 'MySQL is not answering.' }
        }
        if (-not $loginOk) {
            Stop-Setup "The MySQL password was wrong three times. If you forgot it, see 'You forgot the MySQL root password' in README.md."
        }
    }
    if ((Invoke-Helper @('save', '--port', "$MySqlPort")) -ne 0) { Stop-Setup 'Could not write the .env file.' }
    Remove-Item Env:\SRMS_DB_SECRET -ErrorAction SilentlyContinue
    Write-Ok 'MySQL login saved in .env.'
}

Write-Step 'Step 4 of 5: Database tables and demo data'
if ((Invoke-Helper @('ensure-env')) -ne 0) { Stop-Setup 'Could not write the .env file.' }
& $VenvPy (Join-Path $Root 'setup_db.py')
if ($LASTEXITCODE -ne 0) { Stop-Setup 'Creating the database failed (see the message above).' }

Write-Step 'Step 5 of 5: Done'
Write-Ok 'Setup finished. From now on, double-click start.bat to open the app.'
Write-Host '    Demo logins: admin / Admin@123   faculty / Faculty@123   student 241203106130 / Student@123'
$answer = Read-Host '    Start the app now? [Y/n]'
if ($answer -notmatch '^[nN]') {
    Start-Process -FilePath 'explorer.exe' -ArgumentList "`"$(Join-Path $Root 'start.bat')`""
}
Read-Host 'Press Enter to close this window'
