@echo off
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   Conciliador Pro — Backend FastAPI      ║
echo  ║   http://localhost:8000                  ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ── Verificar que Python esté instalado ──────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.10+ desde https://python.org
    pause
    exit /b 1
)

:: ── Detectar si el venv es válido para ESTA ruta ─────────────────────────────
:: El venv guarda la ruta absoluta en pyvenv.cfg — si no coincide, recrearlo
set VENV_OK=0
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -c "import sys; sys.exit(0)" >nul 2>&1
    if not errorlevel 1 set VENV_OK=1
)

if "%VENV_OK%"=="0" (
    echo [INFO] Venv no valido o ruta cambiada. Recreando entorno virtual...
    if exist "venv" rmdir /s /q venv
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el venv.
        pause
        exit /b 1
    )
    echo [INFO] Instalando dependencias...
    venv\Scripts\pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Fallo al instalar dependencias.
        pause
        exit /b 1
    )
    echo [OK] Entorno listo.
)

:: ── Verificar uvicorn ─────────────────────────────────────────────────────────
if not exist "venv\Scripts\uvicorn.exe" (
    echo [INFO] Instalando dependencias faltantes...
    venv\Scripts\pip install -r requirements.txt -q
)

echo.
echo [OK] Iniciando servidor en http://localhost:8000
echo [OK] Presiona Ctrl+C para detener
echo.

venv\Scripts\uvicorn src.api.main_api:app --host 0.0.0.0 --port 8000 --reload

pause
