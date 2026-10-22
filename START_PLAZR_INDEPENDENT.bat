@echo off
title Plazr Autonomous Starter
echo ========================================================
echo    Starting Plazr Services Independently of Antigravity
echo ========================================================
schtasks /run /tn "PlazrAutonomousSupervisor" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\Plazr\supervisor.ps1"
)
echo.
echo [OK] Plazr supervisor is active in the background.
echo Services: PostgreSQL, Redis, Cloudflared Tunnel, Platform Server, Chatbots, and Game Bots.
echo.
timeout /t 3 >nul
