#!/bin/bash

# Nazwa katalogu wirtualnego środowiska
VENV_DIR="venv"

# Sprawdź czy venv istnieje
if [ ! -d "$VENV_DIR" ]; then
    echo "Tworzenie wirtualnego środowiska..."
    python3 -m venv "$VENV_DIR"
fi

# Aktywuj venv
source "$VENV_DIR/bin/activate"

# Zainstaluj zależności
if [ -f "requirements.txt" ]; then
    echo "Instalowanie zależności..."
    pip install -r requirements.txt
fi

# Uruchom aplikację
echo "Uruchamianie aplikacji..."
python3 yt_ai_downloader.py
