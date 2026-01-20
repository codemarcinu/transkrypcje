@echo off
cd /d "%~dp0"

set "VENV_DIR=venv"
set "APP_PATH=src\gui\streamlit_app.py"

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo 🐍 Aktywacja środowiska virtualnego...
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo ⚠️ OSTRZEZENIE: Nie znaleziono venv. Próba uruchomienia systemowego Streamlit...
)

set PYTHONPATH=%PYTHONPATH%;.
echo 🚀 Uruchamianie interfejsu Streamlit...
streamlit run "%APP_PATH%"

if %ERRORLEVEL% neq 0 (
    echo ❌ Wystapil blad podczas uruchamiania aplikacji.
    pause
)
