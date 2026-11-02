@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 photo_manager.py
) else (
  python photo_manager.py
)
pause
