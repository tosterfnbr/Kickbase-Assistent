@echo off
chcp 65001 >nul
title KICKBASE Dashboard - Privater Fernzugriff
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fernzugriff.ps1"
echo.
pause