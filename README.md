# System Generowania Podręczników AI (Map-Reduce)

Projekt przekształca surowe transkrypcje wideo w profesjonalne, ustrukturyzowane rozdziały podręczników IT, wykorzystując architekturę **Map-Reduce** i lokalne modele LLM.

## 🏗️ Architektura

System działa w trzech fazach:

1.  **Pozyskiwanie i Transkrypcja**
    - **YouTube**: Automatyczne pobieranie wideo/audio.
    - **Optymalizacja**: System automatycznie wykrywa i pobiera napisy z YouTube (PL/EN), co pozwala na ominięcie procesu transkrypcji i natychmiastowe przejście do analizy.
    - **Whisper**: Jeśli napisy nie są dostępne, system wykorzystuje modele **Faster-Whisper** do lokalnej transkrypcji z wykorzystaniem GPU.

2.  **Ekstrakcja Wiedzy (Map)**
    - **Agent**: `Extractor` (oparty na **Qwen 2.5 14B**)
    - **Zadanie**: Analizuje tekst fragment po fragmencie, wyciągając kluczowe informacje, techniki i pojęcia.
    - **Wynik**: Baza wiedzy w formacie JSON (`data/processed/`).

3.  **Generowanie Treści (Reduce)**
    - **Agent**: `Writer` (oparty na **Bielik 11B v3**)
    - **Zadanie**: Agreguje zebraną wiedzę i pisze spójny rozdział podręcznika lub opracowanie na zadany temat.
    - **Cechy**: Styl techniczny, inżynierski konkret, brak lania wody.

3.  **Optymalizacja Modelu**
    - Wykorzystujemy customowy model `bielik-writer` z parametrami `repeat_penalty=1.15` (zapobieganie pętlom) i wymuszonym formatem ChatML.

## 📂 Struktura Katalogów

```text
transkrypcje/
├── data/
│   ├── raw/                 # Tu wrzucasz pliki .txt (np. "Narzędziownik...")
│   ├── processed/           # Tu lądują JSON-y z wiedzą (backup co 5 chunków)
│   └── output/              # Gotowe rozdziały .md
├── src/
│   ├── agents/              # Logika agentów (Extractor: Qwen, Writer: Bielik)
│   ├── core/                # Silnik LLM (Ollama wrapper) i czyszczenie tekstu
│   └── utils/               # Konfiguracja (ścieżki, nazwy modeli)
├── main_pipeline.py         # Skrypt uruchomieniowy
├── Modelfile                # Definicja optymalizacji modelu Bielik
└── requirements.txt         # Zależności Python
```

## 🚀 Instalacja i Uruchomienie

### 1. Wymagania
*   **Ollama** zainstalowana i działająca.
*   **Python 3.10+**.
*   **GPU**: Zalecane min. 12GB VRAM (modele ładowane są sekwencyjnie).

### 2. Przygotowanie Modeli
Pobierz Qwena i zbuduj zoptymalizowanego Bielika:

```bash
ollama pull qwen2.5:14b
ollama create bielik-writer -f Modelfile
```

### 3. Instalacja Zależności
```bash
# Wewnątrz venv
pip install -r requirements.txt
```

### 4. Uruchomienie (GUI)
Najwygodniej korzystać z nowoczesnego interfejsu Streamlit:

*   **Windows**: Kliknij dwukrotnie w `start_windows.bat`.
*   **Linux/macOS**: Uruchom `./run_streamlit.sh`.

Interfejs oferuje trzy główne moduły:
- **📺 YouTube**: Pobieranie z opcją automatycznego wykorzystania istniejących napisów (najszybsza metoda).
- **📂 Pliki Lokalne**: Przetwarzanie plików wideo/audio z dysku.
- **📝 Generowanie Treści**: Pozwala na ponowne przetworzenie istniejących transkrypcji i wygenerowanie opracowania na wybrany temat.

> [!NOTE]
> Oryginalny interfejs Tkinter został przeniesiony do `src/gui/legacy/` i można go uruchomić za pomocą `run_legacy_gui.bat` (niepolecane).

### 5. Uruchomienie (CLI)
1.  Wrzuć plik transkrypcji do `data/raw/` (lub użyj istniejącego w `data/output/`).
2.  Uruchom pipeline:
```bash
python main_pipeline.py
```

## 💡 Customizacja

*   **Zmiana Modeli**: Edytuj `src/utils/config.py`.
*   **Zmiana Prompta**:
    *   Prompt ekstrakcji (Qwen): `src/agents/extractor.py`
    *   Prompt pisania (Bielik): `src/agents/writer.py`
    *   System Prompt Bielika: `Modelfile` (wymaga przebudowania modelu `ollama create ...`).

## ⚠️ Rozwiązywanie problemów

*   **Pętle w tekście ("i tak dalej")**: Upewnij się, że używasz modelu `bielik-writer`, który ma ustawione `repetition_penalty`.
*   **Błędy JSON**: Logika w `llm_engine.py` automatycznie czyści Markdown, ale w razie problemów sprawdź surowe odpowiedzi w logach.
