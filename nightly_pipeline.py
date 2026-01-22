#!/usr/bin/env python3
"""
nightly_pipeline.py - Nocny pipeline do przetwarzania listy filmów YouTube.

UŻYCIE:
    1. Edytuj listę YOUTUBE_URLS poniżej LUB utwórz plik urls.txt (jeden URL per linia)
    2. Uruchom: python nightly_pipeline.py
    3. Rano sprawdź batch ID w OpenAI Dashboard lub użyj: python -c "from src.core.batch_manager import BatchManager; print(BatchManager().retrieve_results('BATCH_ID'))"

WYMAGANIA:
    - Zainstalowane zależności projektu (yt-dlp, faster-whisper, openai)
    - Ustawiony OPENAI_API_KEY w .env
    - FFmpeg w PATH (do konwersji audio)
"""

import os
import sys
import gc
import json
import threading
from datetime import datetime
from typing import List, Dict, Optional

# Dodaj główny katalog do PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch

from src.core.downloader import Downloader
from src.core.transcriber import Transcriber
from src.core.batch_manager import BatchManager
from src.core.text_cleaner import clean_transcript
from src.core.gpu_manager import clear_gpu_memory
from src.utils.config import (
    MODEL_EXTRACTOR_OPENAI,
    DATA_RAW,
    DATA_PROCESSED,
    DEFAULT_MODEL_SIZE,
)
from src.utils.prompts_config import EXTRACTION_PROMPT
from src.utils.batch_utils import build_batch_request
from src.utils.helpers import sanitize_filename


# ============================================================================
# KONFIGURACJA - EDYTUJ TUTAJ
# ============================================================================

# Lista URLi YouTube do przetworzenia (alternatywnie: wczytaj z pliku urls.txt)
YOUTUBE_URLS = [
    # "https://www.youtube.com/watch?v=EXAMPLE1",
    # "https://www.youtube.com/watch?v=EXAMPLE2",
]

# Plik z URLami (jeden URL per linia) - ma priorytet nad YOUTUBE_URLS jeśli istnieje
URLS_FILE = "urls.txt"

# Model Whisper (opcje: "medium", "large-v3")
WHISPER_MODEL_SIZE = DEFAULT_MODEL_SIZE  # domyślnie "large-v3"

# Język transkrypcji (None = auto-detekcja, "pl" = polski, "en" = angielski)
TRANSCRIPTION_LANGUAGE = None

# Model OpenAI dla Batch API
OPENAI_MODEL = MODEL_EXTRACTOR_OPENAI  # domyślnie "gpt-4o-mini"


# ============================================================================
# KLASY MOCKUJĄCE (zastępują GUI Streamlit)
# ============================================================================

class ConsoleLogger:
    """Logger wypisujący na konsolę zamiast do GUI Streamlit."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.prefix}{message}")


class DummyStopEvent:
    """Dummy stop_event - nigdy nie jest ustawiony (skrypt działa do końca)."""

    def is_set(self) -> bool:
        return False

    def set(self):
        pass


def console_progress(percent: float, stage: str = ""):
    """Callback postępu wypisujący na konsolę."""
    bar_length = 30
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    print(f"\r  [{bar}] {percent:5.1f}% {stage}", end="", flush=True)
    if percent >= 100:
        print()  # Nowa linia po zakończeniu


# ============================================================================
# FUNKCJE POMOCNICZE
# ============================================================================

def load_urls_from_file(filepath: str) -> List[str]:
    """Wczytuje URLe z pliku tekstowego (jeden URL per linia)."""
    if not os.path.exists(filepath):
        return []

    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Ignoruj puste linie i komentarze
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


# ============================================================================
# GŁÓWNA LOGIKA PIPELINE
# ============================================================================

def process_single_video(
    url: str,
    index: int,
    total: int,
    downloader: Downloader,
    transcriber: Transcriber,
    logger: ConsoleLogger
) -> Optional[Dict]:
    """
    Przetwarza pojedynczy film: pobieranie -> transkrypcja -> czyszczenie.

    Returns:
        Dict z danymi do Batch API lub None w przypadku błędu.
    """
    logger.log(f"{'='*60}")
    logger.log(f"PRZETWARZANIE [{index}/{total}]: {url}")
    logger.log(f"{'='*60}")

    try:
        # --- KROK 1: Pobieranie audio ---
        logger.log("Pobieranie audio z YouTube...")
        downloaded = downloader.download_video(
            url=url,
            save_path=DATA_RAW,
            quality="audio_only",
            audio_quality="128"  # Niższa jakość = szybsze pobieranie
        )

        if not downloaded:
            logger.log("BŁĄD: Nie udało się pobrać żadnego pliku.")
            return None

        # Bierzemy pierwszy (i jedyny) element z listy
        file_info = downloaded[0]
        audio_file = file_info["video"]  # W trybie audio_only to jest plik .mp3
        source_title = file_info.get("source_title", f"video_{index}")
        source_url = file_info.get("source_url", url)

        if not os.path.exists(audio_file):
            logger.log(f"BŁĄD: Plik audio nie istnieje: {audio_file}")
            return None

        logger.log(f"Pobrano: {os.path.basename(audio_file)}")

        # --- KROK 2: Transkrypcja Whisper ---
        logger.log(f"Rozpoczynam transkrypcję (model: {WHISPER_MODEL_SIZE})...")

        segments, info = transcriber.transcribe_video(
            filename=audio_file,
            language=TRANSCRIPTION_LANGUAGE,
            model_size=WHISPER_MODEL_SIZE
        )

        # Zapisz transkrypcję (konsumuje generator)
        output_file, json_file = transcriber.save_transcription(
            segments=segments,
            info=info,
            filename=audio_file,
            output_format="txt",
            language=TRANSCRIPTION_LANGUAGE
        )

        logger.log(f"Transkrypcja zapisana: {os.path.basename(output_file)}")

        # --- KROK 3: Wczytanie i czyszczenie tekstu ---
        with open(output_file, "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = clean_transcript(raw_text)
        logger.log(f"Oczyszczony tekst: {len(cleaned_text)} znaków")

        # --- KROK 4: Czyszczenie pamięci GPU ---
        clear_gpu_memory()
        logger.log("Pamięć GPU wyczyszczona.")

        # --- KROK 5: Budowanie requestu Batch API ---
        custom_id = sanitize_filename(source_title)
        batch_request = build_batch_request(
            custom_id=custom_id,
            transcript_text=cleaned_text,
            model=OPENAI_MODEL
        )

        logger.log(f"Przygotowano request dla Batch API (custom_id: {custom_id})")

        return {
            "request": batch_request,
            "source_url": source_url,
            "source_title": source_title,
            "audio_file": audio_file,
            "transcript_file": output_file
        }

    except InterruptedError as e:
        logger.log(f"Operacja przerwana: {e}")
        return None
    except Exception as e:
        logger.log(f"BŁĄD KRYTYCZNY: {type(e).__name__}: {e}")
        # Czyść pamięć nawet przy błędzie
        clear_gpu_memory()
        return None


def main():
    """Główna funkcja pipeline."""
    print("\n" + "="*70)
    print("   NIGHTLY PIPELINE - Batch Processing dla YouTube")
    print("="*70 + "\n")

    # --- Wczytanie URLi ---
    urls = load_urls_from_file(URLS_FILE)
    if not urls:
        urls = YOUTUBE_URLS

    if not urls:
        print("BŁĄD: Brak URLi do przetworzenia!")
        print(f"  - Dodaj URLe do listy YOUTUBE_URLS w skrypcie")
        print(f"  - LUB utwórz plik '{URLS_FILE}' z listą URLi (jeden per linia)")
        sys.exit(1)

    print(f"Znaleziono {len(urls)} URL(i) do przetworzenia:")
    for i, url in enumerate(urls, 1):
        print(f"  {i}. {url}")
    print()

    # --- Tworzenie katalogów ---
    os.makedirs(DATA_RAW, exist_ok=True)
    os.makedirs(DATA_PROCESSED, exist_ok=True)

    # --- Inicjalizacja komponentów z mockami ---
    logger = ConsoleLogger()
    stop_event = DummyStopEvent()

    downloader = Downloader(
        logger=logger,
        stop_event=stop_event,
        progress_callback=console_progress
    )

    transcriber = Transcriber(
        logger=logger,
        stop_event=stop_event,
        progress_callback=console_progress
    )

    # --- Przetwarzanie sekwencyjne ---
    successful_requests = []
    failed_urls = []

    for i, url in enumerate(urls, 1):
        result = process_single_video(
            url=url,
            index=i,
            total=len(urls),
            downloader=downloader,
            transcriber=transcriber,
            logger=logger
        )

        if result:
            successful_requests.append(result)
        else:
            failed_urls.append(url)

        print()  # Separator między filmami

    # --- Podsumowanie przetwarzania ---
    print("\n" + "="*70)
    print("   PODSUMOWANIE PRZETWARZANIA")
    print("="*70)
    print(f"  Sukces: {len(successful_requests)}/{len(urls)}")
    print(f"  Błędy:  {len(failed_urls)}/{len(urls)}")

    if failed_urls:
        print("\n  Nieudane URLe:")
        for url in failed_urls:
            print(f"    - {url}")

    # --- Wysyłanie Batch do OpenAI ---
    if not successful_requests:
        print("\nBrak poprawnych transkrypcji - nie tworzę Batcha.")
        sys.exit(1)

    print("\n" + "="*70)
    print("   WYSYŁANIE BATCH DO OPENAI")
    print("="*70 + "\n")

    try:
        batch_manager = BatchManager()

        # Przygotuj listę requestów
        requests_list = [r["request"] for r in successful_requests]

        # Utwórz nazwę pliku z timestampem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jsonl_filename = f"nightly_batch_{timestamp}.jsonl"

        # Zapisz do pliku JSONL
        jsonl_path = batch_manager.create_batch_file(requests_list, jsonl_filename)
        logger.log(f"Zapisano plik JSONL: {jsonl_path}")

        # Wyślij do OpenAI
        description = f"Nightly Pipeline {timestamp} - {len(requests_list)} transkrypcji"
        batch_id = batch_manager.upload_and_submit(jsonl_path, description=description)

        print("\n" + "="*70)
        print("   BATCH WYSŁANY POMYŚLNIE!")
        print("="*70)
        print(f"\n  BATCH ID: {batch_id}")
        print(f"\n  Plik JSONL: {jsonl_path}")
        print(f"  Liczba requestów: {len(requests_list)}")
        print(f"\n  Sprawdź status w OpenAI Dashboard:")
        print(f"  https://platform.openai.com/batches")
        print(f"\n  Lub pobierz wyniki komendą:")
        print(f'  python -c "from src.core.batch_manager import BatchManager; bm = BatchManager(); print(bm.retrieve_results(\'{batch_id}\'))"')

        # Zapisz manifest z metadanymi
        manifest = {
            "batch_id": batch_id,
            "timestamp": timestamp,
            "total_urls": len(urls),
            "successful": len(successful_requests),
            "failed": len(failed_urls),
            "failed_urls": failed_urls,
            "files": [
                {
                    "custom_id": r["request"]["custom_id"],
                    "source_url": r["source_url"],
                    "source_title": r["source_title"],
                    "transcript_file": r["transcript_file"]
                }
                for r in successful_requests
            ]
        }

        manifest_path = os.path.join(DATA_PROCESSED, f"nightly_manifest_{timestamp}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        logger.log(f"Manifest zapisany: {manifest_path}")

    except Exception as e:
        print(f"\nBŁĄD WYSYŁANIA BATCHA: {e}")
        print("Transkrypcje zostały zapisane lokalnie - możesz wysłać Batch ręcznie.")
        sys.exit(1)

    print("\n" + "="*70)
    print("   PIPELINE ZAKOŃCZONY")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
