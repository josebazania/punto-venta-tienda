@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)

if errorlevel 1 (
    echo.
    echo La aplicacion se cerro con un error. Revisa logs\pos.log
    pause
)

endlocal
