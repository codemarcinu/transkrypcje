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

3.  **Generowanie Treści (Reduce & PKM)**
    - **Agent**: `Writer` (oparty na **Bielik 11B v3**)
    - **Zadanie**: Agreguje zebraną wiedzę i pisze spójny rozdział w formacie **Obsidian Markdown**.
    - **Cechy**: 
        - **YAML Frontmatter**: Automatyczne metadane (tags, status).
        - **Wikilinks**: Linkowanie narzędzi i pojęć `[[Narzędzie]]`.
        - **Indeks Źródłowy**: Śledzenie pochodzenia wiedzy we fragmentach transkrypcji.

4.  **Zarządzanie Zasobami & Stabilność**
    - **Retry Logic**: System automatycznie ponawia błędy ekstrakcji.
    - **VRAM Optimization**: Wymuszone czyszczenie pamięci GPU (`gc` + `torch.cuda.empty_cache()`) dla stabilnej pracy na kartach 12GB.

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

### 4. Uruchomienie (Windows)

Po prostu kliknij dwukrotnie plik:
`run_app.bat`

> *Skrypt automatycznie aktywuje środowisko i otworzy panel w przeglądarce.*

### 5. Korzystanie
- Wybierz plik transkrypcji z listy po lewej.
- Temat wypełni się automatycznie – możesz go zmienić.
- Kliknij **"Generuj Notatki"**.
- Wynik zobaczysz od razu pod przyciskiem.
- Jeśli masz skonfigurowany **Obsidian Vault**, możesz wysłać notatkę jednym kliknięciem.

> [!TIP]
> Jeśli system zwolni lub zauważysz wysokie zużycie VRAM, użyj przycisku **"Zwolnij VRAM"** w bocznym panelu.

> [!TIP]
> Wszystkie techniczne opcje (wybór modelu, języka, folderów) zostały ukryte w zakładce **"⚙️ Ustawienia Zaawansowane"** w bocznym panelu, aby interfejs pozostawał przejrzysty.

> [!NOTE]
> Oryginalny interfejs Tkinter został przeniesiony do `src/gui/legacy/` i można go uruchomić za pomocą `run_legacy_gui.bat` (niepolecane).

### 6. Uruchomienie (CLI)
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
