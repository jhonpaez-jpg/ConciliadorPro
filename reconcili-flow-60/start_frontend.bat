@echo off
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   Conciliador Pro — Frontend Vite        ║
echo  ║   http://localhost:8080                  ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

if not exist "node_modules" (
    echo [INFO] Instalando dependencias...
    npm install
)

echo [OK] Iniciando frontend...
echo [OK] Presiona Ctrl+C para detener
echo.

npm run dev

pause
