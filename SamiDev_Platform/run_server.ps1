Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:SAMIDEV_TRUST_PROXY = "1"
$env:SAMIDEV_FIREBASE_AUTH = "1"
$env:SAMIDEV_FIREBASE_PROJECT_ID = "samidev-app-092494"
$env:SAMIDEV_FIREBASE_API_KEY = "AIzaSyBPasEuPngaKZ1l-_TgpSkkK03hXQq_dG0"
$env:SAMIDEV_GOOGLE_WEB_CLIENT_ID = "865538421915-thnk94qf4sngume2eaf45pfov56gsvlt.apps.googleusercontent.com"
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\Dev\.samidev\secrets\firebase-admin.json"
$env:SAMIDEV_ADMIN_USERNAME = "admin"
$env:SAMIDEV_ADMIN_PASSWORD = "AdminPassword123!"
$env:SAMIDEV_DATABASE_URL = "postgresql://postgres@127.0.0.1:5432/samidev"
$env:SAMIDEV_REDIS_URL = "redis://127.0.0.1:6379/0"
$env:PYTHONUNBUFFERED = "1"

python -u start_dev.py --port 56648 --storage persistent --public-origin "https://plazr.net" --no-browser
