#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "--- COFOG-Panel GUI Launcher (Safe Mode) ---"

# 1. Find Python
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3 is not installed. Please install it from python.org"
    exit 1
fi

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating a safe virtual environment in .venv folder..."
    $PYTHON_CMD -m venv .venv
fi

# 3. Activate Virtual Environment
source .venv/bin/activate

# 4. Install/Update Dependencies
echo "Checking/Installing dependencies inside the virtual environment..."
pip install --upgrade pip
if ! pip install -e ".[gui]"; then
    echo
    echo "Error: pip could not install COFOG-Panel and Streamlit, so the GUI cannot start."
    echo "Check the internet connection and the messages above, then run this script again."
    exit 1
fi

# 5. Run Streamlit
echo "Starting GUI... The browser window should open automatically."
streamlit run gui.py
