@echo off
setlocal EnableDelayedExpansion
title Conciliador Pro — Backend

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║         Conciliador Pro — Backend FastAPI            ║
echo  ║         http://localhost:8000                        ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ── 1. Verificar / instalar Python ───────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Python no encontrado. Intentando instalar con winget...
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo [INFO] winget no disponible. Descargando instalador de Python...
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
        "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
        del "%TEMP%\python_installer.exe" >nul 2>&1
    )
    :: Refrescar PATH
    call refreshenv >nul 2>&1
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] No se pudo instalar Python automaticamente.
        echo         Instala Python 3.10+ manualmente desde https://python.org
        echo         Asegurate de marcar "Add Python to PATH" durante la instalacion.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Python instalado correctamente.
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v encontrado.

:: ── 2. Verificar / recrear venv ──────────────────────────────────────────────
set VENV_OK=0
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -c "import sys; sys.exit(0)" >nul 2>&1
    if not errorlevel 1 set VENV_OK=1
)

if "%VENV_OK%"=="0" (
    echo [INFO] Creando entorno virtual...
    if exist "venv" rmdir /s /q venv >nul 2>&1
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

:: ── 3. Instalar / actualizar dependencias ────────────────────────────────────
if not exist "venv\Scripts\uvicorn.exe" (
    echo [INFO] Instalando dependencias (primera vez, puede tardar unos minutos)...
    venv\Scripts\pip install -r requirements.txt -q --no-warn-script-location
    if errorlevel 1 (
        echo [ERROR] Fallo al instalar dependencias.
        pause
        exit /b 1
    )
    echo [OK] Dependencias instaladas.
) else (
    echo [OK] Dependencias ya instaladas.
)

:: ── 4. Iniciar servidor ───────────────────────────────────────────────────────
echo.
echo [OK] Iniciando servidor en http://localhost:8000
echo [OK] Acceso en red local: http://%COMPUTERNAME%:8000
echo [OK] Presiona Ctrl+C para detener
echo.

venv\Scripts\uvicorn src.api.main_api:app --host 0.0.0.0 --port 8000 --reload

pause
