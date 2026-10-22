# Stop all Plazr processes and supervisor cleanly
Write-Host "Stopping Plazr services..."

# 1. Stop supervisor
$sups = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*supervisor.ps1*" }
foreach ($p in $sups) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

# 2. Stop bots
$bots = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run_chatbots*" -or $_.CommandLine -like "*run_worker*" }
foreach ($p in $bots) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

$pyBots = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*chat-bots*" -or $_.CommandLine -like "*pool-bots*" }
foreach ($p in $pyBots) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

# 3. Stop server & gamehost
$srv = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run_server.ps1*" }
foreach ($p in $srv) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

$pySrv = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*start_dev.py*" -or $_.CommandLine -like "*backend\app.py*" }
foreach ($p in $pySrv) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

$nodeSrv = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*gamehost*" }
foreach ($p in $nodeSrv) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

# 4. Stop Cloudflared
Stop-Process -Name "cloudflared" -Force -ErrorAction SilentlyContinue

# 5. Stop Redis
Stop-Process -Name "redis-server" -Force -ErrorAction SilentlyContinue

# 6. Stop Postgres
Stop-Process -Name "postgres" -Force -ErrorAction SilentlyContinue

Write-Host "All Plazr services have been stopped."
