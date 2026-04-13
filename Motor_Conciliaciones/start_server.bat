@echo off
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   Conciliador Pro — Backend FastAPI      ║
echo  ║   http://localhost:8000                  ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\uvicorn.exe" (
    echo [ERROR] No se encontro uvicorn en el venv.
    echo Ejecuta: venv\Scripts\pip install uvicorn
    pause
    exit /b 1
)

echo [OK] Iniciando servidor...
echo [OK] Presiona Ctrl+C para detener
echo.

venv\Scripts\uvicorn src.api.main_api:app --host 0.0.0.0 --port 8000 --reload

pause
