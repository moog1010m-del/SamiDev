@echo off
setlocal EnableExtensions DisableDelayedExpansion
title SamiDev V25 - Carrom and Table Soccer

rem Run this file from the fully EXTRACTED V25 project folder.
rem This launcher runs the local development stack; data is kept in memory.
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto folder_error

echo ==========================================================
echo   SamiDev V25 - Carrom and Table Soccer
echo ==========================================================
echo Project: "%CD%"
echo.

if not exist "start_dev.py" goto missing_project
if not exist "backend\requirements.txt" goto missing_project
if not exist "gamehost\server.js" goto missing_project
if not exist "game\main.js" goto missing_project
if not exist "game\games\tablesoccer\main.js" goto missing_v25
if not exist "game\platform\index.html" goto missing_v25
if not exist "game\platform\build.json" goto missing_v25
if not exist "game\samidev-integrity.json" goto missing_v25
findstr /L /C:"choose-tablesoccer" "game\platform\index.html" >nul 2>&1
if errorlevel 1 goto missing_v25

echo [1/4] Checking Node.js 22 or newer...
where node >nul 2>&1
if errorlevel 1 goto missing_node
node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 22 ? 0 : 1)" >nul 2>&1
if errorlevel 1 goto missing_node

echo [2/4] Preparing Python 3.12 or newer...
if exist ".venv\Scripts\python.exe" goto check_venv

py -3.12 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 goto use_py312
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 goto use_py3
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 goto use_python
goto missing_python

:use_py312
set "SAMIDEV_LAUNCH_PY=py -3.12"
goto create_venv

:use_py3
set "SAMIDEV_LAUNCH_PY=py -3"
goto create_venv

:use_python
set "SAMIDEV_LAUNCH_PY=python"
goto create_venv

:create_venv
echo Creating the project's Python environment...
%SAMIDEV_LAUNCH_PY% -m venv ".venv"
if errorlevel 1 goto venv_error

:check_venv
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 goto venv_error

echo [3/4] Installing or checking project dependencies...
echo The first setup requires an internet connection.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "backend\requirements.txt"
if errorlevel 1 goto dependencies_error

rem Select this local project's assets and its own GameHost.
rem Ignore inherited production shard addresses and obsolete bundle overrides.
set "SAMIDEV_GAME_DIR=%CD%\game"
set "SAMIDEV_GAMEHOST_URLS="
set "SAMIDEV_MAINJS_SHA256="
set "SAMIDEV_PRODUCTION=0"

echo.
echo [4/4] Starting both games and verifying the served V25 interface...
echo After sign-in, enter a community and click the Table Soccer game card.
echo The browser opens only after all platform files pass verification.
echo Keep this window open. Press Ctrl+C to stop the local services.
echo Local development data is lost when the services stop.
echo.
".venv\Scripts\python.exe" -u "start_dev.py"
set "SAMIDEV_LAUNCH_EXIT=%ERRORLEVEL%"
echo.
if "%SAMIDEV_LAUNCH_EXIT%"=="0" goto stopped
echo SamiDev stopped with error code %SAMIDEV_LAUNCH_EXIT%.
echo Please copy the error displayed above if you need help.
goto finish

:stopped
echo SamiDev has stopped.
goto finish

:missing_project
echo ERROR: Project files were not found beside this launcher.
echo Extract the V25 ZIP, then run START_SAMIDEV.bat inside the extracted folder.
goto failed

:missing_v25
echo ERROR: This folder does not contain the complete V25 two-game build.
echo Extract SamiDev_Platform_V25_UI_Fix.zip and use that folder.
goto failed

:missing_node
echo ERROR: Node.js 22 or newer must be installed and available on PATH.
echo Install Node.js, close this window, and run this file again.
goto failed

:missing_python
echo ERROR: Python 3.12 or newer was not found.
echo Install Python with the Python launcher or enable Add Python to PATH.
echo Close this window and run this file again.
goto failed

:venv_error
echo ERROR: The local Python environment could not be created or used.
echo Check Python 3.12+ and write access to the extracted project folder.
echo If .venv came from another computer, rename it and try again.
goto failed

:dependencies_error
echo ERROR: Python dependencies could not be installed.
echo Check the error above and your internet connection, then run again.
goto failed

:failed
set "SAMIDEV_LAUNCH_EXIT=1"

:finish
echo.
pause
popd
exit /b %SAMIDEV_LAUNCH_EXIT%

:folder_error
echo ERROR: Cannot open the folder containing this launcher.
echo Extract the V25 project into a writable folder and try again.
pause
exit /b 1
