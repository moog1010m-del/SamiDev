Set-Location $PSScriptRoot
$g = Get-Content "C:\Users\Dev\.samidev\secrets\gemini.json" | ConvertFrom-Json
$b = Get-Content "C:\Users\Dev\.samidev\secrets\bot_sessions.json" | ConvertFrom-Json

$env:GEMINI_API_KEY = $g.GEMINI_API_KEY
$env:GEMINI_MODEL = "gemini-flash-lite-latest"
$b.psobject.properties | ForEach-Object {
    Set-Item "env:$($_.Name)" $_.Value
}
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

python -u run.py live --enable-live --use-gemini --config config.json --base-url http://127.0.0.1:56648
