# Plazr Autonomous Master Supervisor
# Runs 24/7 independently of Antigravity or any IDE.
# Manages: PostgreSQL, Redis, Cloudflared, Platform Server, Chatbots, and Pool Bots.

$ErrorActionPreference = "Continue"
$logsDir = "C:\Plazr\logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$supervisorLog = "$logsDir\supervisor.log"

function Log-Info($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Output $line
    Add-Content -Path $supervisorLog -Value $line -Encoding utf8
}

# Single-instance enforcement
$currentPid = $PID
$existing = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessId -ne $currentPid -and $_.CommandLine -like "*supervisor.ps1*"
}
if ($existing) {
    Log-Info "Supervisor is already running (PID: $($existing[0].ProcessId)). Exiting duplicate instance."
    exit 0
}

Log-Info "=================================================="
Log-Info "Plazr Master Autonomous Supervisor Starting (PID: $currentPid)"
Log-Info "=================================================="

function Test-PortListening($port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        return ($null -ne $conn)
    } catch {
        return $false
    }
}

function Test-ProcessByCmd($name, $filter) {
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name = '$name'" -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -like "*$filter*"
        }
        return ($null -ne $procs)
    } catch {
        return $false
    }
}

function Ensure-Postgres {
    if (-not (Test-PortListening 5432)) {
        Log-Info "PostgreSQL is not listening on 5432. Starting PostgreSQL..."
        $pgExe = "C:\Users\Dev\.samidev\bin\pgsql\bin\postgres.exe"
        $pgArgs = "-D C:\Users\Dev\.samidev\storage\postgres -p 5432"
        Start-Process -FilePath $pgExe -ArgumentList $pgArgs -RedirectStandardOutput "$logsDir\postgres.log" -RedirectStandardError "$logsDir\postgres_err.log" -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }
}

function Ensure-Redis {
    if (-not (Test-PortListening 6379)) {
        Log-Info "Redis is not listening on 6379. Starting Redis..."
        $redisExe = "C:\Users\Dev\.samidev\bin\redis-server.exe"
        $redisArgs = "--port 6379 --dir C:\Users\Dev\.samidev\storage\redis --appendonly yes --appendfsync everysec --maxmemory-policy noeviction"
        Start-Process -FilePath $redisExe -ArgumentList $redisArgs -RedirectStandardOutput "$logsDir\redis.log" -RedirectStandardError "$logsDir\redis_err.log" -WindowStyle Hidden
        Start-Sleep -Seconds 1
    }
}

function Ensure-Cloudflared {
    $cf = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
    if (-not $cf) {
        Log-Info "Cloudflared is not running. Starting Cloudflare tunnel..."
        $cfExe = "C:\Users\Dev\Desktop\IPASigner\cloudflared.exe"
        $cfArgs = "tunnel run samidev-tunnel"
        Start-Process -FilePath $cfExe -ArgumentList $cfArgs -RedirectStandardOutput "$logsDir\cloudflared.log" -RedirectStandardError "$logsDir\cloudflared_err.log" -WindowStyle Hidden
        Start-Sleep -Seconds 2
    }
}

function Ensure-PlatformServer {
    if (Test-PortListening 5432 -and (Test-PortListening 6379)) {
        if (-not (Test-PortListening 56648)) {
            Log-Info "Platform Server is not listening on 56648. Starting Platform Server..."
            Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File C:\Plazr\SamiDev_Platform\run_server.ps1" -WorkingDirectory "C:\Plazr\SamiDev_Platform" -RedirectStandardOutput "$logsDir\platform_server.log" -RedirectStandardError "$logsDir\platform_server_err.log" -WindowStyle Hidden
            Start-Sleep -Seconds 3
        }
    }
}

function Ensure-Chatbots {
    $running = Test-ProcessByCmd "python.exe" "chat-bots\run.py"
    if (-not $running) {
        $launcherRunning = Test-ProcessByCmd "powershell.exe" "run_chatbots.ps1"
        if (-not $launcherRunning) {
            Log-Info "Chatbots daemon is not running. Starting Chatbots..."
            Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File C:\Plazr\experiments\chat-bots\run_chatbots.ps1" -WorkingDirectory "C:\Plazr\experiments\chat-bots" -RedirectStandardOutput "$logsDir\chatbots.log" -RedirectStandardError "$logsDir\chatbots_err.log" -WindowStyle Hidden
            Start-Sleep -Seconds 1
        }
    }
}

function Ensure-PoolBots {
    $running = Test-ProcessByCmd "python.exe" "pool-bots\worker.py"
    if (-not $running) {
        $launcherRunning = Test-ProcessByCmd "powershell.exe" "run_worker.ps1"
        if (-not $launcherRunning) {
            Log-Info "Pool/Multigame bots daemon is not running. Starting Worker..."
            Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File C:\Plazr\experiments\pool-bots\run_worker.ps1" -WorkingDirectory "C:\Plazr\experiments\pool-bots" -RedirectStandardOutput "$logsDir\pool_bots.log" -RedirectStandardError "$logsDir\pool_bots_err.log" -WindowStyle Hidden
            Start-Sleep -Seconds 1
        }
    }
}

# Initial Startup sequence
Ensure-Postgres
Ensure-Redis
Start-Sleep -Seconds 2
Ensure-Cloudflared
Ensure-PlatformServer
Start-Sleep -Seconds 3
Ensure-Chatbots
Ensure-PoolBots

Log-Info "Initial startup check complete. Entering autonomous monitoring loop..."

# Autonomous 24/7 Monitoring Loop
$loopCount = 0
while ($true) {
    Start-Sleep -Seconds 10
    $loopCount++

    Ensure-Postgres
    Ensure-Redis
    Ensure-Cloudflared
    Ensure-PlatformServer
    Ensure-Chatbots
    Ensure-PoolBots

    # Heartbeat log every 10 minutes (60 iterations)
    if ($loopCount % 60 -eq 0) {
        $pg = Test-PortListening 5432
        $rd = Test-PortListening 6379
        $srv = Test-PortListening 56648
        $cf = [bool](Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue)
        Log-Info "Supervisor Heartbeat - PG:$pg Redis:$rd Server:$srv Tunnel:$cf"
    }
}
