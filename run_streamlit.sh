#!/bin/bash

# Configuration
VENV_DIR="venv"
APP_PATH="src/gui/streamlit_app.py"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "⚠️ BŁĄD: Katalog venv nie istnieje. Uruchom najpierw ./run.sh aby zainstalować środowisko."
    exit 1
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Verify streamlit installation
if ! pip show streamlit > /dev/null 2>&1; then
    echo "📦 Instalowanie Streamlit..."
    pip install streamlit watchdog
fi

# Run Streamlit
export PYTHONPATH=$PYTHONPATH:.
echo "🚀 Uruchamianie interfejsu Streamlit..."
echo "Aplikacja otworzy się w przeglądarce (zazwyczaj http://localhost:8501)"
streamlit run "$APP_PATH" --server.headless false
