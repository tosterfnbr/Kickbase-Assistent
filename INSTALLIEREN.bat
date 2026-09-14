@echo off
chcp 65001 >nul
title KICKBASE Assistent - Installation
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause