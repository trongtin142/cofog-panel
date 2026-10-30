@echo off
setlocal

cd /d %~dp0

echo --- COFOG-Panel GUI Launcher (Safe Mode) ---

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python from python.org and ensure 'Add to PATH' is checked.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
if not exist ".venv" (
    echo Creating a safe virtual environment in .venv folder...
    python -m venv .venv
)

:: 3. Activate Virtual Environment
call .venv\Scripts\activate

:: 4. Install/Update Dependencies
echo Checking/Installing dependencies inside the virtual environment...
python -m pip install --upgrade pip
pip install -e ".[gui]"

:: 5. Run Streamlit
echo Starting GUI... The browser window should open automatically.
streamlit run gui.py

if %errorlevel% neq 0 (
    echo.
    echo An error occurred.
    pause
)
