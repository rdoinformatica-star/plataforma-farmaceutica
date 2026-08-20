@echo off
chcp 65001 >nul
title Pharma Intelligence - Instalacao
cd /d "%~dp0"

set "PY=C:\Users\Home\AppData\Local\Programs\Python\Python312\python.exe"

echo ============================================
echo   PHARMA INTELLIGENCE - Instalacao
echo ============================================
echo.

if not exist "%PY%" (
  echo [ERRO] Python 3.12 nao encontrado em:
  echo        %PY%
  echo        Instale o Python 3.12 e rode este arquivo de novo.
  pause
  exit /b 1
)

echo [1/3] Criando o ambiente Python...
if not exist "backend\.venv\Scripts\python.exe" (
  "%PY%" -m venv backend\.venv
  if errorlevel 1 goto :erro
)

echo [2/3] Instalando as bibliotecas do servidor...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto :erro

echo [3/3] Instalando as bibliotecas da interface...
call npm install --prefix frontend
if errorlevel 1 goto :erro

echo.
echo ============================================
echo   Instalacao concluida.
echo   Agora use: iniciar.bat
echo ============================================
pause
exit /b 0

:erro
echo.
echo [ERRO] A instalacao falhou. Veja a mensagem acima.
pause
exit /b 1
