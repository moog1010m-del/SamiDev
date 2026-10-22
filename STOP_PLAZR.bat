@echo off
title Stop Plazr
echo Stopping all Plazr services...
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Plazr\stop_services.ps1"
echo [OK] Done.
timeout /t 3 >nul
