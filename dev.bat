@echo off
chcp 65001 >nul
title Pharma Intelligence - Desenvolvimento
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================
echo   MODO DESENVOLVIMENTO (--reload ligado)
echo.
echo   AVISO: o servidor reinicia sozinho a cada
echo   alteracao no codigo. Se isso acontecer no
echo   meio de uma importacao, ela e perdida.
echo   Para uso normal, prefira iniciar.bat
echo ============================================
echo.

start "Pharma API" backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
start "Pharma Web" cmd /c "npm run dev --prefix frontend"
timeout /t 7 >nul
start "" http://localhost:3000
exit /b 0
