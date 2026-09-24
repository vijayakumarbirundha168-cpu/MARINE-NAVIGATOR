@echo off
title PHANTOM STRIKERS - Antarctic Navigation Decision Support
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py
  goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
  python app.py
  goto :end
)
echo.
echo Python 3 was not found.
echo Install Python 3 and enable "Add Python to PATH".
echo Then double-click START_DASHBOARD.bat again.
echo.
pause
:end
