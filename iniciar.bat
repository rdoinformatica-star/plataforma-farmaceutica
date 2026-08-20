@echo off
chcp 65001 >nul
title Pharma Intelligence
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERRO] O sistema ainda nao foi instalado.
  echo        Rode primeiro o arquivo: instalar.bat
  pause
  exit /b 1
)

netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo [AVISO] A porta 8000 ja esta em uso.
  echo         Se o Pharma Intelligence ja estiver aberto, use parar.bat antes.
  pause
  exit /b 1
)

netstat -ano | findstr ":3000 " | findstr "LISTENING" >nul
if not errorlevel 1 (
  echo [AVISO] A porta 3000 ja esta em uso.
  echo         Se o Pharma Intelligence ja estiver aberto, use parar.bat antes.
  pause
  exit /b 1
)

echo Iniciando o Pharma Intelligence...
start "Pharma API" /min backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
start "Pharma Web" /min cmd /c "npm run dev --prefix frontend"

echo Aguardando o servidor subir...
timeout /t 7 >nul
start "" http://localhost:3000

echo.
echo Pronto. O sistema abriu no navegador: http://localhost:3000
echo Para desligar, use: parar.bat
timeout /t 4 >nul
exit /b 0
