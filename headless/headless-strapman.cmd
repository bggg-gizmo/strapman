@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%CD%\headless\launch.py" %*
) else (
  python "%CD%\headless\launch.py" %*
)
set "STRAPMAN_EXIT_CODE=%errorlevel%"
endlocal & exit /b %STRAPMAN_EXIT_CODE%
