@echo off
cd /d "%~dp0\.."
python tools\load_test.py --players 1000 --concurrency 100 --hold 1
pause
