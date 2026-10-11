@echo off
setlocal
cd /d "%~dp0"
if not exist .env (
  echo ERROR: .env is required for production.
  echo Copy .env.example to .env and set the allowed origin and GameHost service key.
  exit /b 1
)
docker compose up --build -d
if errorlevel 1 (
  echo Docker Compose failed. Make sure Docker Desktop is installed and running and production secrets are set.
  exit /b 1
)
echo.
echo SamiDev production origin is listening on the configured bind address ^(default 127.0.0.1:8088^).
echo Expose it only through your HTTPS/WSS TLS edge using the same domain configured in SAMIDEV_ALLOWED_ORIGINS.
echo Do not publish the raw HTTP origin directly to the Internet.
endlocal
