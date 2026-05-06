@echo off
echo Ya tienes instalado NodeJS? Si no, puedes descargarlo desde https://nodejs.org/
echo Instalando dependecia e iniciando servidor...
cmd /k "cd /d "%~dp0" && npm install && npm run dev"
