#!/bin/bash

# Katalog skryptu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Nazwa katalogu wirtualnego środowiska
VENV_DIR=".venv"
PID_FILE=".gradio.pid"

# Sprawdź czy venv istnieje i ma poprawną strukturę (Linux)
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Tworzenie wirtualnego środowiska..."
    rm -rf "$VENV_DIR"  # Usuń jeśli istnieje ale jest uszkodzony
    python3 -m venv "$VENV_DIR"

    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        echo "BŁĄD: Nie udało się utworzyć środowiska wirtualnego"
        exit 1
    fi
fi

# Aktywuj venv
source "$VENV_DIR/bin/activate"

# Zainstaluj zależności
if [ -f "requirements.txt" ]; then
    echo "Sprawdzanie zależności..."
    pip install -q -r requirements.txt
fi

# Sprawdź czy aplikacja już działa
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Aplikacja już działa (PID: $OLD_PID)"
        echo "Użyj ./stop.sh aby zatrzymać"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# Uruchom aplikację Gradio
echo "========================================"
echo "  AI Transkrypcja & Notatki v2.0"
echo "========================================"
echo ""
echo "Uruchamianie na http://localhost:7860"
echo ""

# Uruchom w tle i zapisz PID
python3 -m src.gui.gradio_app &
APP_PID=$!
echo $APP_PID > "$PID_FILE"

echo "Aplikacja uruchomiona (PID: $APP_PID)"
echo "Użyj ./stop.sh aby zatrzymać"
echo ""

# Czekaj na proces
wait $APP_PID
rm -f "$PID_FILE"
