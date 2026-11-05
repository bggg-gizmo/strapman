@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0install.py"
) else (
  python "%~dp0install.py"
)
if errorlevel 1 (
  echo.
  echo Strapman could not start. Check the error above.
  pause
)
endlocal
