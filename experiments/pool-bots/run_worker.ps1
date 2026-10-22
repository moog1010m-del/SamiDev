Set-Location $PSScriptRoot
$s = Get-Content "C:\Users\Dev\.samidev\secrets\admin_session.txt"
$env:PLAZR_POOL_WORKER_ADMIN_SESSION = $s.Trim()
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Continuous supervisor loop for game worker:
# - Joins human games promptly (within 3 seconds)
# - Plays bot-vs-bot in Saudi room (majlis) to keep tables active (10 games = 20 bots)
# - Always keeps 30 bots in reserve for immediate human matching
# - Auto-restarts on any connection drop
while ($true) {
    python -u worker.py --base-url http://127.0.0.1:56648 --enable-play --join-after 3 --bot-vs-bot --selfplay-per-room 20 --reserve-per-room 30
    Write-Host "Worker process exited. Restarting in 3 seconds..."
    Start-Sleep -Seconds 3
}
