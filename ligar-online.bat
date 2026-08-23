@echo off
chcp 65001 >nul
title Pharma Intelligence - Online
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set CLOUDFLARED="C:\Program Files (x86)\cloudflared\cloudflared.exe"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERRO] O sistema ainda nao foi instalado.
  echo        Rode primeiro o arquivo: instalar.bat
  pause
  exit /b 1
)

if not exist %CLOUDFLARED% (
  echo [ERRO] cloudflared nao encontrado em %CLOUDFLARED%
  echo        Instale com: winget install --id Cloudflare.cloudflared -e
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

echo Iniciando o Pharma Intelligence (modo online)...
start "Pharma API" /min backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
start "Pharma Web" /min cmd /c "npm run dev --prefix frontend"

echo Aguardando os servidores subirem...
timeout /t 7 >nul

echo Abrindo o tunel publico (Cloudflare)...
start "Pharma Tunnel" cmd /k %CLOUDFLARED% tunnel --url http://127.0.0.1:3000

echo.
echo ==========================================================
echo   O link publico vai aparecer na janela "Pharma Tunnel"
echo   que acabou de abrir. Procure a linha:
echo.
echo       https://alguma-coisa.trycloudflare.com
echo.
echo   Esse e o link pra acessar de qualquer lugar. Ele muda
echo   toda vez que voce roda este script de novo.
echo.
echo   IMPORTANTE: sem senha. Nao divulgue esse link em publico.
echo   NAO FECHE nenhuma das 3 janelas (API / Web / Tunnel) -
echo   fechar qualquer uma delas derruba o acesso.
echo.
echo   Para desligar tudo, use: parar.bat
echo ==========================================================
timeout /t 5 >nul
start "" http://localhost:3000
exit /b 0
