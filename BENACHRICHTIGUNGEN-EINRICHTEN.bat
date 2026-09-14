@echo off
chcp 65001 >nul
title KICKBASE Benachrichtigungen
"%LOCALAPPDATA%\KickbaseAssistent\.venv\Scripts\python.exe" "%LOCALAPPDATA%\KickbaseAssistent\benachrichtigungen.py"
echo.
pause