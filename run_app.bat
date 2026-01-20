@echo off
:: run_app.bat - Główny skrypt startowy dla Windows
:: Cel: Automatyczna aktywacja venv i start Streamlit bez pytania o zgody.

cd /d "%~dp0"

:: 1. Sprawdzenie i aktywacja środowiska wirtualnego
IF EXIST "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) ELSE (
    echo [BLAD] Nie znaleziono folderu venv.
    echo Upewnij sie, ze zainstalowales projekt (uruchom install.bat lub pip install -r requirements.txt)
    pause
    exit /b
)

:: 2. Uruchomienie interfejsu Streamlit
echo [INFO] Uruchamianie interfejsu Streamlit...
echo [INFO] Aplikacja otworzy sie w Twojej przegladarce.
streamlit run src/gui/streamlit_app.py

:: 3. Pauza w razie błędu (żeby okno nie zniknęło natychmiast)
if %errorlevel% neq 0 pause
