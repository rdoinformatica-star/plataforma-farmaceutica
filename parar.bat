@echo off
chcp 65001 >nul
title Pharma Intelligence - Parar
echo Desligando o Pharma Intelligence...
taskkill /FI "WINDOWTITLE eq Pharma API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Pharma Web*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Pharma Tunnel*" /T /F >nul 2>&1
echo Pronto.
timeout /t 3 >nul
exit /b 0
