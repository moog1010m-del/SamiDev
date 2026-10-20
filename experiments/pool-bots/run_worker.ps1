Set-Location $PSScriptRoot
$s = Get-Content "C:\Users\Dev\.samidev\secrets\admin_session.txt"
$env:PLAZR_POOL_WORKER_ADMIN_SESSION = $s.Trim()
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Run worker without --bot-vs-bot:
# Bots will NEVER play against each other.
# They will ONLY join when a human player requests/creates a table, joining after 5 seconds.
python -u worker.py --base-url http://127.0.0.1:56648 --enable-play --join-after 5
