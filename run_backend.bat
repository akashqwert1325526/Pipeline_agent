@echo off
title PipelineMedic Backend
cd /d "%~dp0backend"
echo ========================================================
echo  Starting PipelineMedic Backend on http://127.0.0.1:8000
echo  API Documentation: http://127.0.0.1:8000/docs
echo ========================================================
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
pause
