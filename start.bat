@echo off
title PipelineMedic Launcher
echo ========================================================
echo  Launching PipelineMedic (Backend + Frontend)
echo ========================================================
start "PipelineMedic Backend" "%~dp0run_backend.bat"
timeout /t 2 /nobreak >nul
start "PipelineMedic Frontend" "%~dp0run_frontend.bat"
timeout /t 3 /nobreak >nul
echo Opening browser...
start http://localhost:5173
echo PipelineMedic is running!
pause
