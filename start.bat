@echo off
rem Opens the backend and both demo pages, always with the project's own Python.
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo venv not found. Run: python -m venv venv
  echo Then: venv\Scripts\python -m pip install -r requirements.txt
  pause
  exit /b 1
)
start "Backend 8000" cmd /k venv\Scripts\python -m uvicorn backend.main:app --port 8000
start "MarkGrid 5500" cmd /k venv\Scripts\python -m http.server 5500 -d demo/markgrid
start "Two99 5501" cmd /k venv\Scripts\python -m http.server 5501 -d demo/two99
