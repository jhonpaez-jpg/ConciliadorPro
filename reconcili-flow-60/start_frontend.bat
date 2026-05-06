@echo off

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] NodeJS no esta instalado.
    echo.
    echo Por favor instala NodeJS desde:
    echo https://nodejs.org/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [OK] %%v NodeJS detectado.


echo Instalando dependecia e iniciando servidor...
cmd /k "cd /d "%~dp0" && npm install && npm run dev"
