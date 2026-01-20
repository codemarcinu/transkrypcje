# Marcin's YT & Local Media Transcriber v3.2

Aplikacja desktopowa do pobierania wideo z YouTube (w tym playlist), transkrypcji audio (Whisper) oraz generowania podsumowań (Ollama).

## 🚀 Funkcje

- **Pobieranie wideo/audio**: Obsługa pojedynczych linków YouTube oraz playlist.
- **Transkrypcja AI**: Wykorzystuje model `faster-whisper` (możliwość wyboru modelu i języka).
- **Podsumowania AI**: Integracja z `Ollama` do generowania podsumowań tekstu.
- **Przetwarzanie lokalne**: Możliwość wskazania plików audio/wideo z dysku.
- **Konwersja**: Automatyczna konwersja do MP3 (FFmpeg).
- **Logowanie**: Podgląd logów w czasie rzeczywistym.

## 🛠️ Wymagania

- **System**: Linux / Windows / macOS
- **Python**: 3.8+
- **FFmpeg**: Zainstalowany i dostępny w PATH.
- **Ollama**: Uruchomiony serwer Ollama.
- **Model AI**: Zalecany `bielik-11b-v3.0-instruct:Q5_K_M` dla analizy OSINT.

## 📦 Instalacja

1.  **Klonowanie repozytorium** (lub wypakowanie kodu).
2.  **Stworzenie środowiska wirtualnego** (zalecane):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate   # Windows
    ```
3.  **Instalacja zależności**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Instalacja Tkinter** (jeśli wymagane, np. na Linux):
    ```bash
    sudo apt-get install python3-tk
    ```

## ▶️ Uruchomienie

### Linux / macOS
```bash
./run.sh
```
Lub ręcznie:
```bash
source venv/bin/activate
python3 main.py
```

### Windows
Uruchom `run_app.bat`.

## 📂 Struktura Projektu

Projekt został zrefaktoryzowany do architektury modułowej:

```
.
├── src/
│   ├── core/               # Logika biznesowa
│   │   ├── downloader.py   # Obsługa yt-dlp i ffmpeg
│   │   ├── transcriber.py  # Obsługa faster-whisper
│   │   ├── summarizer.py   # Obsługa Ollama
│   │   └── processor.py    # Fasada (Processor)
│   ├── gui/                # Interfejs użytkownika
│   │   └── app.py          # Główna klasa aplikacji (Tkinter)
│   └── utils/              # Narzędzia
│       ├── config.py       # Konfiguracja i stałe
│       ├── helpers.py      # Funkcje pomocnicze
│       └── logger.py       # System logowania
├── main.py                 # Punkt wejściowy aplikacji
├── run.sh                  # Skrypt startowy (Linux)
├── run_app.bat             # Skrypt startowy (Windows)
└── requirements.txt        # Zależności
```

## 📝 Licencja
Projekt prywatny.
