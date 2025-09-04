@echo off
echo Starting local development server...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

REM Setup local database
echo Setting up local database...
python setup_local_db.py

REM Start local server
echo Starting local server...
python run.py

pause
