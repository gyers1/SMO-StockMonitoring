@echo off
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 goto :missing
if not exist .venv\Scripts\python.exe uv venv --python 3.14 .venv
uv pip sync --python .venv\Scripts\python.exe requirements-lock.txt
if errorlevel 1 exit /b 1
set "PATH=%CD%\.venv\Scripts;%SystemRoot%\System32;%SystemRoot%"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name SMO --icon "assets\smo.ico" --add-data "assets:assets" --add-data "korean_stocks.json:." --add-data "THIRD_PARTY_NOTICES.md:." SMO.py
if errorlevel 1 exit /b 1
for /f %%V in ('.venv\Scripts\python.exe -c "from app_version import VERSION; print(VERSION)"') do set "SMO_VERSION=%%V"
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=%SMO_VERSION% installer.iss
exit /b %errorlevel%
:missing
echo Install uv first: https://docs.astral.sh/uv/getting-started/installation/
exit /b 1
