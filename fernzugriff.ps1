$ErrorActionPreference = "Stop"
Write-Host "Privater Fernzugriff über Tailscale" -ForegroundColor Cyan

$Tailscale = Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"
if (-not (Test-Path $Tailscale)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget wurde nicht gefunden. Bitte Tailscale von https://tailscale.com/download/windows installieren."
    }
    Write-Host "Tailscale wird installiert. Eine Windows-Abfrage kann erscheinen."
    winget install --id Tailscale.Tailscale --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Tailscale konnte nicht installiert werden." }
}

if (-not (Test-Path $Tailscale)) {
    throw "Tailscale wurde installiert. Bitte Windows neu starten und diese Datei erneut öffnen."
}

Write-Host "Bitte jetzt im geöffneten Browser bei Tailscale anmelden."
& $Tailscale up
if ($LASTEXITCODE -ne 0) { throw "Die Tailscale-Anmeldung wurde nicht abgeschlossen." }

Write-Host "Das Dashboard wird ausschließlich in deinem privaten Tailscale-Netz freigegeben."
& $Tailscale serve --bg 8765
if ($LASTEXITCODE -ne 0) { throw "Tailscale Serve konnte nicht aktiviert werden." }

Write-Host "Fernzugriff eingerichtet:" -ForegroundColor Green
& $Tailscale serve status
Write-Host "Installiere Tailscale auch auf deinem Handy und melde dich dort mit demselben Konto an."