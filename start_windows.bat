@echo off
set "VENV_DIR=venv"
set "APP_PATH=src\gui\streamlit_app.py"

if not exist "%VENV_DIR%" (
    echo ⚠️ BLAD: Katalog venv nie istnieje.
    pause
    exit /b 1
)

set PYTHONPATH=%PYTHONPATH%;.
echo 🚀 Uruchamianie interfejsu Streamlit...
"%VENV_DIR%\Scripts\python.exe" -m streamlit run "%APP_PATH%"
pause
