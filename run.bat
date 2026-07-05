@echo off
echo Starting Sirius Market Intelligence Engine...
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start the FastAPI server
echo Starting backend on http://localhost:8000
echo API docs: http://localhost:8000/docs
echo.
uvicorn app.main:app --reload --port 8000

REM Deactivate on exit
call deactivate
