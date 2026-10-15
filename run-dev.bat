@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe uv venv --python 3.14 .venv
uv pip sync --python .venv\Scripts\python.exe requirements-lock.txt
if errorlevel 1 exit /b 1
start "" .venv\Scripts\pythonw.exe SMO.py
