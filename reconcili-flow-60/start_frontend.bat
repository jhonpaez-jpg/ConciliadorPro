@echo off
setlocal EnableDelayedExpansion
title Conciliador Pro — Frontend

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║         Conciliador Pro — Frontend Vite              ║
echo  ║         https://localhost:8080                       ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ── 1. Verificar / instalar Node.js ──────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Node.js no encontrado. Intentando instalar con winget...
    winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        echo [INFO] winget no disponible. Descargando instalador de Node.js...
        powershell -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v20.11.0/node-v20.11.0-x64.msi' -OutFile '%TEMP%\node_installer.msi'"
        msiexec /i "%TEMP%\node_installer.msi" /quiet /norestart
        del "%TEMP%\node_installer.msi" >nul 2>&1
    )
    :: Refrescar PATH
    call refreshenv >nul 2>&1
    node --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERROR] No se pudo instalar Node.js automaticamente.
        echo         Instala Node.js 18+ manualmente desde https://nodejs.org
        echo.
        pause
        exit /b 1
    )
    echo [OK] Node.js instalado correctamente.
)

for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [OK] Node.js %%v encontrado.

:: ── 2. Instalar dependencias npm ─────────────────────────────────────────────
if not exist "node_modules" (
    echo [INFO] Instalando dependencias npm (primera vez, puede tardar unos minutos)...
    npm install --silent
    if errorlevel 1 (
        echo [ERROR] Fallo npm install.
        pause
        exit /b 1
    )
    echo [OK] Dependencias instaladas.
) else (
    echo [OK] Dependencias ya instaladas.
)

:: ── 3. Iniciar frontend ───────────────────────────────────────────────────────
echo.
echo [OK] Iniciando frontend en https://localhost:8080
echo [OK] Acceso en red local: https://%COMPUTERNAME%:8080
echo [INFO] Primera vez: el navegador mostrara advertencia de certificado.
echo        Haz clic en "Avanzado" y luego "Continuar" para aceptarlo.
echo [OK] Presiona Ctrl+C para detener
echo.

npm run dev

pause
