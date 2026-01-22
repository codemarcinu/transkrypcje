"""
Stałe dla interfejsu Gradio.
- Etykiety UI (po polsku)
- Opcje stylów
- Formaty wyjściowe
- Komunikaty błędów
"""

from typing import Dict, List, Tuple

# =============================================================================
# ETYKIETY UI
# =============================================================================

LABELS = {
    # Główne
    "app_title": "Sekurak Transcriber & Analyst v2.0",
    "app_subtitle": "Wydajne przetwarzanie lokalne: Whisper + Bielik + Qwen",

    # Sidebar
    "sidebar_title": "Konfiguracja",
    "system_status": "Status systemu",
    "language_label": "Jezyk nagrania",
    "ai_settings": "Ustawienia AI",
    "model_label": "Model rozpoznawania mowy",
    "model_info": "large-v3 = lepsza jakosc, medium = szybszy",
    "llm_provider_label": "Silnik AI",
    "llm_provider_info": "ollama = lokalny (darmowy), openai = chmura (platny)",
    "tasks_title": "Co zrobic?",
    "task_transcribe": "Zamien mowe na tekst",
    "task_extract": "Przeanalizuj tresc (dla notatek)",
    "task_summarize": "Wygeneruj krotkie podsumowanie",
    "advanced_options": "Opcje zaawansowane",
    "output_format_label": "Format transkrypcji",
    "output_format_info": "json = z metadanymi, txt = czysty tekst",
    "download_subs_label": "Pobierz napisy z YouTube (jesli dostepne)",
    "summary_style_label": "Styl podsumowania",
    "obsidian_vault_label": "Sciezka do Obsidian Vault",
    "obsidian_vault_placeholder": "/sciezka/do/vault",
    "clear_vram_btn": "Zwolnij VRAM",
    "cancel_btn": "Anuluj operacje",

    # Tab 1: Transkrypcja
    "tab1_title": "Nowa Transkrypcja",
    "tab1_desc": "Zamien nagranie na tekst",
    "tab1_hint": "Wklej link YouTube lub wgraj plik audio/wideo",
    "youtube_section": "Z YouTube",
    "youtube_url_label": "Link do filmu",
    "youtube_url_placeholder": "https://www.youtube.com/watch?v=...",
    "local_section": "Z pliku",
    "local_file_label": "Wybierz pliki audio/wideo",
    "start_btn": "Rozpocznij",
    "status_log_label": "Dziennik zdarzen",
    "create_note_btn": "Stworz notatke z tej transkrypcji",

    # Tab 2: Notatki
    "tab2_title": "Stworz Notatke",
    "tab2_desc": "Wygeneruj notatke z transkrypcji",
    "kb_file_label": "Wybierz transkrypcje",
    "refresh_btn": "Odswiez",
    "generate_btn": "Generuj Notatke",
    "generation_status": "Status generowania",
    "customize_section": "Dostosuj notatke",
    "topic_label": "Temat notatki",
    "topic_placeholder": "Zostaw puste = automatyczny z nazwy pliku",
    "topic_info": "Opcjonalne - domyslnie uzyje nazwy pliku",
    "style_label": "Styl opracowania",
    "style_info": "Wybierz jak Bielik ma sformatowac tresc",
    "advanced_section": "Zaawansowane",
    "metrics_title": "Metryki bazy wiedzy",
    "segments_label": "Segmenty",
    "concepts_label": "Koncepty",
    "tools_label": "Narzedzia",
    "tips_label": "Wskazowki",
    "metadata_title": "Metadane (dla Obsidian)",
    "source_url_label": "URL zrodla",
    "source_title_label": "Tytul zrodla",
    "duration_label": "Czas trwania",
    "aliases_label": "Aliasy (oddzielone przecinkiem)",
    "custom_prompts_title": "Wlasne prompty",
    "system_prompt_label": "System prompt",
    "user_prompt_label": "User prompt",
    "reset_prompts_btn": "Przywroc domyslne",
    "preview_label": "Podglad",
    "edit_label": "Edycja",
    "save_section": "Zapisz",
    "filename_label": "Nazwa pliku",
    "save_obsidian_btn": "Zapisz do Obsidian",
    "save_local_btn": "Zapisz lokalnie",
    "download_btn": "Pobierz",
    "tags_label": "Wykryte tagi",

    # Tab 3: Batch
    "tab3_title": "Przetwarzanie Zbiorcze",
    "tab3_desc": "Przetworz wiele filmow naraz",
    "batch_urls_label": "Adresy URL (jeden na linie)",
    "batch_urls_placeholder": "https://www.youtube.com/watch?v=abc123\nhttps://www.youtube.com/watch?v=def456",
    "urls_count_label": "Liczba URLi",
    "batch_start_btn": "Rozpocznij przetwarzanie",
    "batch_log_label": "Log przetwarzania",
    "batch_history_title": "Historia zadan",
    "refresh_history_btn": "Odswiez historie",
    "batch_id_label": "ID zadania",
    "batch_id_placeholder": "batch_...",
    "retrieve_btn": "Pobierz wyniki",
    "import_btn": "Importuj notatki",
}

# =============================================================================
# OPCJE STYLÓW
# =============================================================================

# Format: (klucz_backend, etykieta_ui, opis)
STYLE_OPTIONS: List[Tuple[str, str, str]] = [
    ("note", "Standardowa Notatka", "Zbalansowany, edukacyjny. TL;DR na gorze, krotkie akapity."),
    ("deep_dive", "Deep Dive (Szczegolowy)", "Analityczny, gleboki, wyczerpujacy temat."),
    ("summary", "Streszczenie Exec", "Krotkie podsumowanie dla zapracowanych."),
    ("tags_only", "Tylko Tagi", "Generuje tylko tagi bez tresci."),
]

# Mapowanie etykiet UI na klucze backendu
STYLE_MAP: Dict[str, str] = {label: key for key, label, _ in STYLE_OPTIONS}

# Lista etykiet dla dropdown
STYLE_CHOICES: List[str] = [label for _, label, _ in STYLE_OPTIONS]

# Opisy stylów
STYLE_DESCRIPTIONS: Dict[str, str] = {label: desc for _, label, desc in STYLE_OPTIONS}

# =============================================================================
# FORMATY WYJŚCIOWE
# =============================================================================

OUTPUT_FORMAT_OPTIONS: List[Tuple[str, str]] = [
    ("json", "JSON (z metadanymi)"),
    ("txt", "TXT (z timestamps)"),
    ("txt_no_timestamps", "TXT (czysty tekst)"),
    ("srt", "SRT (napisy)"),
    ("vtt", "VTT (napisy web)"),
]

OUTPUT_FORMAT_CHOICES: List[str] = [label for _, label in OUTPUT_FORMAT_OPTIONS]
OUTPUT_FORMAT_MAP: Dict[str, str] = {label: key for key, label in OUTPUT_FORMAT_OPTIONS}

# =============================================================================
# STYLE PODSUMOWAŃ
# =============================================================================

SUMMARY_STYLE_OPTIONS: List[str] = [
    "Zwiezle (3 punkty)",
    "Krotkie (1 akapit)",
    "Szczegolowe",
]

# =============================================================================
# KOMUNIKATY BŁĘDÓW
# =============================================================================

ERROR_MESSAGES: Dict[str, str] = {
    "no_url": "Blad: Podaj adres URL",
    "no_file": "Blad: Wybierz plik do przetworzenia",
    "invalid_url": "Blad: Nieprawidlowy format URL (musi zaczynac sie od http:// lub https://)",
    "download_failed": "Blad pobierania: {details}\n\nMozliwe przyczyny:\n- Nieprawidlowy URL\n- Film niedostepny lub prywatny\n- Problem z polaczeniem internetowym",
    "transcription_failed": "Blad transkrypcji: {details}\n\nSprawdz:\n- Czy plik audio jest prawidlowy\n- Czy masz wystarczajaco VRAM (min. 6GB dla large-v3)",
    "extraction_failed": "Blad ekstrakcji wiedzy: {details}",
    "generation_failed": "Blad generowania notatki: {details}",
    "tagging_failed": "Blad generowania tagow: {details}",
    "save_failed": "Blad zapisywania: {details}",
    "ollama_unavailable": "Ollama niedostepna!\n\nUpewnij sie, ze Ollama jest uruchomiona:\n$ ollama serve",
    "vram_insufficient": "Niewystarczajaca pamiec VRAM.\n\nSprobuj:\n1. Kliknij 'Zwolnij VRAM' w sidebarze\n2. Uzyj mniejszego modelu (medium zamiast large-v3)\n3. Zamknij inne aplikacje uzywajace GPU",
    "cancelled": "Operacja anulowana przez uzytkownika.",
    "no_kb_file": "Blad: Wybierz plik bazy wiedzy",
    "kb_file_not_found": "Blad: Plik bazy wiedzy nie istnieje",
    "no_content": "Blad: Brak tresci do zapisania - najpierw wygeneruj notatke",
    "no_filename": "Blad: Podaj nazwe pliku",
    "invalid_obsidian_path": "Blad: Nieprawidlowa sciezka do Obsidian Vault - sprawdz ustawienia",
}


def format_error(error_key: str, details: str = "") -> str:
    """
    Formatuje komunikat błędu dla użytkownika.

    Args:
        error_key: Klucz błędu z ERROR_MESSAGES
        details: Szczegóły błędu do wstawienia

    Returns:
        Sformatowany komunikat błędu
    """
    template = ERROR_MESSAGES.get(error_key, f"Nieznany blad: {details}")
    return template.format(details=details)


# =============================================================================
# KOMUNIKATY SUKCESU
# =============================================================================

SUCCESS_MESSAGES: Dict[str, str] = {
    "download_complete": "Pobieranie zakonczone: {filename}",
    "transcription_complete": "Transkrypcja zakonczona: {filename}",
    "extraction_complete": "Ekstrakcja wiedzy zakonczona ({chunks} fragmentow)",
    "generation_complete": "Notatka wygenerowana pomyslnie",
    "save_complete": "Zapisano: {filepath}",
    "obsidian_save_complete": "Zapisano do Obsidian: {filename}",
    "vram_cleared": "VRAM zwolniony. Wolne: {free_gb:.1f} GB / {total_gb:.1f} GB",
    "cancelled": "Operacja anulowana",
}


def format_success(success_key: str, **kwargs) -> str:
    """
    Formatuje komunikat sukcesu.

    Args:
        success_key: Klucz sukcesu z SUCCESS_MESSAGES
        **kwargs: Parametry do wstawienia

    Returns:
        Sformatowany komunikat sukcesu
    """
    template = SUCCESS_MESSAGES.get(success_key, "Operacja zakonczona")
    return template.format(**kwargs)


# =============================================================================
# TYPY PLIKÓW
# =============================================================================

ALLOWED_AUDIO_EXTENSIONS = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"]
ALLOWED_VIDEO_EXTENSIONS = [".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv"]
ALLOWED_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS + ALLOWED_VIDEO_EXTENSIONS

# Dla gr.File
FILE_TYPES = [
    ".mp4", ".mp3", ".m4a", ".wav", ".mkv", ".avi", ".mov", ".webm", ".flac"
]

# =============================================================================
# DOMYŚLNE WARTOŚCI
# =============================================================================

DEFAULTS = {
    "language": "Polski",
    "model_size": "large-v3",
    "output_format": "json",
    "style": "Standardowa Notatka",
    "summary_style": "Zwiezle (3 punkty)",
    "do_transcribe": True,
    "do_extract": True,
    "do_summarize": False,
    "download_subs": True,
    "auto_tag": True,
}
