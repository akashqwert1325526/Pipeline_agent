@echo off
title PipelineMedic Frontend
cd /d "%~dp0frontend"
echo ========================================================
echo  Starting PipelineMedic Frontend on http://localhost:5173
echo ========================================================
npm run dev
pause
