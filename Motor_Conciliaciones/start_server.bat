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

:: ── 1. Verificar Python ───────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado.
    echo.
    echo Por favor instala Python 3.11 o 3.12 desde:
    echo https://www.python.org/downloads/
    echo IMPORTANTE: Marca "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v detectado.

:: ── 2. Crear entorno virtual si no existe ─────────────────
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

:: ── 3. Activar entorno virtual ────────────────────────────
call venv\Scripts\activate

:: ── 4. Actualizar pip ─────────────────────────────────────
echo [INFO] Actualizando pip...
python -m pip install --upgrade pip >nul 2>&1

:: ── 5. Instalar dependencias SIEMPRE ──────────────────────
if not exist "requirements.txt" (
    echo [ERROR] No se encontro requirements.txt
    pause
    exit /b 1
)

echo [INFO] Instalando dependencias (esto puede tardar)...
pip install -r requirements.txt --upgrade --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] Fallo instalando dependencias.
    echo Intentando reparar entorno...
    
    :: Intento de reparación automática
    pip install --upgrade setuptools wheel
    pip install -r requirements.txt
    
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar dependencias.
        pause
        exit /b 1
    )
)

echo [OK] Dependencias listas.

:: ── 6. Validar librerias críticas ─────────────────────────
echo [INFO] Verificando librerias necesarias...

python -c "import uvicorn, fastapi, xlsxwriter" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Faltan librerias criticas.
    echo Intentando instalar manualmente...
    pip install uvicorn fastapi XlsxWriter
    
    python -c "import uvicorn, fastapi, xlsxwriter" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudieron cargar las librerias necesarias.
        pause
        exit /b 1
    )
)

echo [OK] Librerias verificadas.

:: ── 7. Iniciar servidor ───────────────────────────────────
:start_server
echo.
echo [OK] Iniciando servidor en http://localhost:8000
echo [OK] Presiona Ctrl+C para detener
echo.

python -m uvicorn src.api.main_api:app --host 0.0.0.0 --port 8000 --reload

echo.
echo [INFO] Servidor detenido.
pause
goto start_server