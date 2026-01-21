#!/bin/bash

# Skrypt do bezpiecznego zatrzymywania aplikacji Streamlit

echo "🔍 Szukanie uruchomionej aplikacji Streamlit..."

# Szukanie PID procesu streamlit run src/gui/streamlit_app.py
# Używamy pgrep -f dla dopasowania pełnej komendy
PID=$(pgrep -f "streamlit run src/gui/streamlit_app.py")

if [ -z "$PID" ]; then
    echo "⚠️ Nie znaleziono uruchomionej aplikacji Streamlit."
    exit 0
fi

echo "🛑 Zatrzymywanie procesów Streamlit (PID: $PID)..."

# Próba grzecznego zamknięcia
kill $PID

# Czekamy chwilę i sprawdzamy czy proces zniknął
sleep 2

if ps -p $PID > /dev/null; then
    echo "⏳ Aplikacja nie zamknęła się grzecznie, wymuszam (SIGKILL)..."
    kill -9 $PID
fi

echo "✅ Aplikacja została zatrzymana."
