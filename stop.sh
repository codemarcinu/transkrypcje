#!/bin/bash

# Katalog skryptu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE=".gradio.pid"

echo "========================================"
echo "  Zatrzymywanie AI Transkrypcja"
echo "========================================"
echo ""

# Metoda 1: Użyj zapisanego PID
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Zatrzymywanie aplikacji (PID: $PID)..."
        kill "$PID" 2>/dev/null
        sleep 2

        # Sprawdź czy proces się zatrzymał
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Wymuszanie zatrzymania..."
            kill -9 "$PID" 2>/dev/null
        fi

        rm -f "$PID_FILE"
        echo "Aplikacja zatrzymana."
    else
        echo "Proces $PID nie istnieje."
        rm -f "$PID_FILE"
    fi
else
    echo "Brak pliku PID. Szukam procesów Gradio..."
fi

# Metoda 2: Znajdź procesy po nazwie (fallback)
GRADIO_PIDS=$(pgrep -f "gradio_app" 2>/dev/null)

if [ -n "$GRADIO_PIDS" ]; then
    echo "Znaleziono procesy Gradio: $GRADIO_PIDS"
    for pid in $GRADIO_PIDS; do
        echo "Zatrzymywanie PID: $pid"
        kill "$pid" 2>/dev/null
    done
    sleep 2

    # Sprawdź ponownie i wymuś zatrzymanie jeśli potrzeba
    REMAINING=$(pgrep -f "gradio_app" 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        echo "Wymuszanie zatrzymania pozostałych procesów..."
        for pid in $REMAINING; do
            kill -9 "$pid" 2>/dev/null
        done
    fi
    echo "Wszystkie procesy Gradio zatrzymane."
else
    echo "Brak uruchomionych procesów Gradio."
fi

# Wyczyść plik PID na wszelki wypadek
rm -f "$PID_FILE"

echo ""
echo "Gotowe."
