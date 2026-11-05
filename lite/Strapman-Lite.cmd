@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%CD%\install.py" --edition lite
) else (
  python "%CD%\install.py" --edition lite
)
if errorlevel 1 (
  echo.
  echo Lite could not launch. Read the error above.
  pause
  exit /b 1
)
endlocal
