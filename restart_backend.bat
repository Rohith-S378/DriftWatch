@echo off
echo Stopping any running uvicorn...
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak >nul

echo Starting fresh backend with SQLite...
cd C:\Users\DELL\.openclaw\workspace\sirius-main
call .\venv\Scripts\activate.bat
pip install aiosqlite -q
uvicorn app.main:app --reload --port 8000
