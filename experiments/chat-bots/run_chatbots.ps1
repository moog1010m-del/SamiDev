Set-Location $PSScriptRoot
$g = Get-Content "C:\Users\Dev\.samidev\secrets\gemini.json" | ConvertFrom-Json
$b = Get-Content "C:\Users\Dev\.samidev\secrets\bot_sessions.json" | ConvertFrom-Json

$allKeys = @()
if ($g.GEMINI_API_KEYS) {
    foreach ($k in $g.GEMINI_API_KEYS) {
        if ($k -and $k.Trim() -ne "" -and -not $k.StartsWith("PUT_KEY_")) {
            $allKeys += $k.Trim()
        }
    }
}
if ($g.GEMINI_API_KEY -and $g.GEMINI_API_KEY.Trim() -ne "") {
    if ($allKeys -notcontains $g.GEMINI_API_KEY.Trim()) {
        $allKeys += $g.GEMINI_API_KEY.Trim()
    }
}

$env:GEMINI_API_KEY = ($allKeys -join ",")
$env:GEMINI_MODEL = "gemini-flash-lite-latest"
$b.psobject.properties | ForEach-Object {
    Set-Item "env:$($_.Name)" $_.Value
}
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

while ($true) {
    python -u run.py live --enable-live --use-gemini --config config.json --base-url http://127.0.0.1:56648
    Write-Host "[*] Chatbot daemon restarted automatically. Waiting 3s..."
    Start-Sleep -Seconds 3
}
