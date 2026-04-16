@echo off
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   Conciliador Pro — Frontend Vite        ║
echo  ║   http://localhost:8080                  ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ── Verificar Node.js ─────────────────────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js no encontrado. Instala Node.js desde https://nodejs.org
    pause
    exit /b 1
)

:: ── Instalar dependencias si faltan o si package.json cambió ─────────────────
if not exist "node_modules" (
    echo [INFO] Instalando dependencias npm...
    npm install
    if errorlevel 1 (
        echo [ERROR] Fallo npm install.
        pause
        exit /b 1
    )
)

echo.
echo [OK] Iniciando frontend en http://localhost:8080
echo [OK] Presiona Ctrl+C para detener
echo.

npm run dev

pause
