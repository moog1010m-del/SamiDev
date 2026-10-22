Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:SAMIDEV_TRUST_PROXY = "1"
$env:SAMIDEV_FIREBASE_AUTH = "1"
$env:SAMIDEV_FIREBASE_PROJECT_ID = "samidev-app-092494"
$env:SAMIDEV_FIREBASE_API_KEY = "AIzaSyBPasEuPngaKZ1l-_TgpSkkK03hXQq_dG0"
$env:SAMIDEV_GOOGLE_WEB_CLIENT_ID = "865538421915-thnk94qf4sngume2eaf45pfov56gsvlt.apps.googleusercontent.com"
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\Dev\.samidev\secrets\firebase-admin.json"
$env:SAMIDEV_FIREBASE_ADMIN_UID = "e9ZZU64SD4UnLKXYWXLktCnbmLq1"
$env:SAMIDEV_ADMIN_USERNAME = "admin"
$env:SAMIDEV_ADMIN_PASSWORD = "AdminPassword123!"
$env:SAMIDEV_DATABASE_URL = "postgresql://postgres@127.0.0.1:5432/samidev"
$env:SAMIDEV_REDIS_URL = "redis://127.0.0.1:6379/0"
$env:PYTHONUNBUFFERED = "1"

# Load only Xsolla server settings from the private local environment file.
# Do not echo values: API keys and webhook secrets must remain server-side.
$xsollaEnvPath = Join-Path $PSScriptRoot '.env'
if (Test-Path -LiteralPath $xsollaEnvPath) {
    foreach ($xsollaLine in Get-Content -LiteralPath $xsollaEnvPath) {
        if ($xsollaLine -match '^\s*(XSOLLA_(?:ENABLED|SANDBOX|PROJECT_ID|API_KEY|WEBHOOK_SECRET|RETURN_URL))\s*=(.*)$') {
            $xsollaName = $Matches[1]
            $xsollaValue = $Matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($xsollaName, $xsollaValue, 'Process')
        }
    }
    Remove-Variable xsollaLine, xsollaValue, xsollaName -ErrorAction SilentlyContinue
}

while ($true) {
    python -u start_dev.py --port 56648 --storage persistent --public-origin "https://plazr.net" --no-browser
    Write-Host "Platform server exited. Restarting in 3 seconds..."
    Start-Sleep -Seconds 3
}
