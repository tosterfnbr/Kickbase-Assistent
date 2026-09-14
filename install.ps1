$ErrorActionPreference = "Stop"
$InstallDir = Join-Path $env:LOCALAPPDATA "KickbaseAssistent"

Write-Host "KICKBASE Assistent wird eingerichtet..." -ForegroundColor Cyan

function Find-Python {
    $Candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:ProgramFiles "Python312\python.exe"),
        (Join-Path $env:ProgramFiles "Python313\python.exe")
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) { return $Candidate }
    }
    $Command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($Command -and $Command.Source -notlike "*WindowsApps*") { return $Command.Source }
    return $null
}

$BasePython = Find-Python
if (-not $BasePython) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Python fehlt und winget ist nicht vorhanden. Bitte Python 3.12 aus dem Microsoft Store installieren."
    }
    Write-Host "Python wird installiert..."
    winget install --id Python.Python.3.12 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Die Python-Installation über winget ist fehlgeschlagen (Code $LASTEXITCODE)." }
    $BasePython = Find-Python
    if (-not $BasePython) {
        throw "Python wurde installiert, konnte aber noch nicht gefunden werden. Windows bitte einmal neu starten und INSTALLIEREN.bat erneut ausführen."
    }
}

# Eine bereits laufende alte Dashboard-Version sauber beenden, damit das Update sofort sichtbar wird.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { ($_.Name -eq "pythonw.exe" -or $_.Name -eq "python.exe") -and $_.CommandLine -like "*$InstallDir*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot "app.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "decision_engine.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "ligainsider.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "stats_provider.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "requirements.txt") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "einrichten.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "dashboard.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "dashboard.html") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "launcher.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "benachrichtigungen.py") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "BENACHRICHTIGUNGEN-EINRICHTEN.bat") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "strategie.json") $InstallDir -Force
Copy-Item (Join-Path $PSScriptRoot "config.example.json") $InstallDir -Force

if (-not (Test-Path (Join-Path $InstallDir ".venv\Scripts\python.exe"))) {
    & $BasePython -m venv (Join-Path $InstallDir ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Die Python-Umgebung konnte nicht erstellt werden." }
}
$Python = Join-Path $InstallDir ".venv\Scripts\python.exe"
& $Python -m pip install --disable-pip-version-check --upgrade pip
& $Python -m pip install -r (Join-Path $InstallDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Python-Abhängigkeiten konnten nicht installiert werden." }

$ConfigPath = Join-Path $InstallDir "config.json"
if (-not (Test-Path $ConfigPath)) {
    Write-Host "Jetzt werden E-Mail, Passwort und Liga lokal eingerichtet." -ForegroundColor Yellow
    & $Python (Join-Path $InstallDir "einrichten.py")
} else {
    Write-Host "Vorhandene Anmeldung, E-Mail-Einstellungen und Handelsregeln bleiben erhalten." -ForegroundColor Green
}

$StartupDir = [Environment]::GetFolderPath("Startup")
$StartupFile = Join-Path $StartupDir "Kickbase-Assistent.cmd"
$Pythonw = Join-Path $InstallDir ".venv\Scripts\pythonw.exe"
$AppFile = Join-Path $InstallDir "launcher.py"
$StartupContent = '@start "" /min "' + $Pythonw + '" "' + $AppFile + '" --loop'
Set-Content -Path $StartupFile -Value $StartupContent -Encoding Ascii

Write-Host "Verbindungstest läuft..." -ForegroundColor Cyan
& $Python (Join-Path $InstallDir "app.py") --once
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installation eingerichtet, aber der Verbindungstest ist fehlgeschlagen." -ForegroundColor Red
    Write-Host "Bitte einen Screenshot dieser Meldung senden."
    exit $LASTEXITCODE
}

Write-Host "Installation abgeschlossen." -ForegroundColor Green
Write-Host "Ordner: $InstallDir"
Write-Host "Der Assistent startet künftig bei deiner Windows-Anmeldung automatisch."
$EmailReady = $false
try { $EmailReady = [bool]((Get-Content $ConfigPath -Raw | ConvertFrom-Json).email_notifications) } catch {}
if (-not $EmailReady) {
    $NotifySetup = Read-Host "E-Mail-Benachrichtigungen jetzt einrichten? (J/N)"
    if ($NotifySetup -match "^[JjYy]") {
        & $Python (Join-Path $InstallDir "benachrichtigungen.py")
    }
} else {
    Write-Host "E-Mail-Benachrichtigungen sind bereits eingerichtet." -ForegroundColor Green
}
Start-Process $Pythonw -ArgumentList ('"' + $AppFile + '" --loop') -WorkingDirectory $InstallDir
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8765"