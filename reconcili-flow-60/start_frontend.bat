@echo off
setlocal

title Conciliador Pro - Frontend

echo.
echo ==========================================
echo   Conciliador Pro - Frontend
echo   http://localhost:5173
echo ==========================================
echo.

cd /d "%~dp0"

set "NODE_EXE=C:\Program Files\nodejs\node.exe"
set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"

if not exist "%NODE_EXE%" (
    echo [ERROR] Node.js no encontrado en:
    echo   %NODE_EXE%
    echo.
    echo Descargalo desde: https://nodejs.org
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('"%NODE_EXE%" --version') do echo [OK] Node %%v detectado

if not exist "%NPM_CMD%" (
    echo [ERROR] npm no encontrado. Reinstala Node.js.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('"%NPM_CMD%" --version') do echo [OK] npm %%v detectado

if not exist "package.json" (
    echo [ERROR] package.json no encontrado en %CD%
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo.
    echo [INFO] Instalando dependencias, espera...
    "%NPM_CMD%" install
    if errorlevel 1 (
        echo [ERROR] Fallo npm install.
        pause
        exit /b 1
    )
)

echo [OK] Todo listo. Iniciando servidor...
echo.
echo   Abre en el navegador: http://localhost:5173
echo   Presiona Ctrl+C para detener.
echo.

"%NPM_CMD%" run dev

echo.
echo [INFO] Servidor detenido.
pause
