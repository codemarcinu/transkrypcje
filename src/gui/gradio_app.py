"""
Gradio GUI dla AI Transkrypcja & Notatki v2.0
"""

import gradio as gr
import os
import sys
import json
import glob
import threading
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Generator

import torch

# Dodanie ścieżki projektu do sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.core.processor import ContentProcessor
from src.core.downloader import Downloader
from src.core.transcriber import Transcriber
from src.agents.writer import ReportWriter
from src.agents.extractor import KnowledgeExtractor
from src.utils.prompts_config import PROMPT_TEMPLATES, EXTRACTION_PROMPT
from src.utils.logger import setup_logger
from src.utils.config import (
    WHISPER_LANGUAGES, WHISPER_MODELS, DEFAULT_MODEL_SIZE,
    DATA_PROCESSED, DATA_OUTPUT, DATA_RAW, CHUNK_SIZE, OVERLAP,
    MODEL_EXTRACTOR, MODEL_EXTRACTOR_OPENAI, LLM_PROVIDER, OPENAI_API_KEY,
    OBSIDIAN_VAULT_PATH, OBSIDIAN_EXPORT_ENABLED, OBSIDIAN_SUBFOLDER
)
from src.utils.helpers import check_ffmpeg, sanitize_filename
from src.core.text_cleaner import clean_transcript
from src.utils.text_processing import smart_split_text
from src.core.llm_engine import unload_model
from src.core.batch_manager import BatchManager
from src.core.gpu_manager import clear_gpu_memory
from src.utils.batch_utils import build_batch_request

logger = setup_logger()

# =============================================================================
# SEKCJA 2: KLASY POMOCNICZE I HELPERY
# =============================================================================

CUSTOM_SETTINGS_FILE = os.path.join(DATA_PROCESSED, "custom_settings.json")

def save_custom_settings(style, system, user):
    """Zapisuje własne ustawienia do pliku JSON."""
    try:
        data = {"style": style, "system": system, "user": user}
        with open(CUSTOM_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return "✅ Ustawienia zapisane na stałe"
    except Exception as e:
        return f"❌ Błąd zapisu: {e}"

def load_custom_settings():
    """Wczytuje własne ustawienia z pliku JSON."""
    if os.path.exists(CUSTOM_SETTINGS_FILE):
        try:
            with open(CUSTOM_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("style", "standard"), data.get("system"), data.get("user")
        except:
            pass
    return "standard", None, None

class GradioProgress:
    """Adapter progress callback dla Gradio."""

    def __init__(self, progress: gr.Progress):
        self.progress = progress
        self.stage_map = {
            "downloading": "Pobieranie wideo...",
            "converting": "Przygotowywanie audio...",
            "transcribing": "Przetwarzanie mowy (Whisper)...",
            "summarizing": "Generowanie podsumowania...",
            "content_generation": "Bielik pisze rozdział...",
            "cleaning": "Porządkowanie plików..."
        }

    def update(self, percent: float, stage: str, file_size: Optional[str] = None):
        val = min(max(percent / 100.0, 0.0), 1.0)
        friendly_stage = self.stage_map.get(stage.lower(), f"Pracuję: {stage}")
        desc = f"{friendly_stage}"
        if file_size:
            desc += f" | Rozmiar: {file_size}"
        self.progress(val, desc=desc)


class DummyStopEvent:
    """Dummy stop_event - nigdy nie jest ustawiony."""
    def is_set(self) -> bool:
        return False
    def set(self):
        pass


class SimpleLogger:
    """Prosty logger dla komponentów."""
    def __init__(self, log_func=None):
        self.log_func = log_func

    def log(self, message: str):
        if self.log_func:
            self.log_func(message)
        else:
            print(message)


# =============================================================================
# SEKCJA 3: FUNKCJE TAB 1 - PRZETWARZANIE AUDIO
# =============================================================================

def run_knowledge_extraction_internal(
    txt_file: str,
    progress: gr.Progress,
    start_pct: float = 0.6,
    end_pct: float = 0.95
) -> Optional[str]:
    """Wewnętrzna funkcja ekstrakcji wiedzy."""
    if not txt_file or not os.path.exists(txt_file):
        return None

    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        clean_text = clean_transcript(raw_text)
        chunks = smart_split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)

        if not chunks:
            return None

        knowledge_base = []
        extractor = KnowledgeExtractor()
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            progress_pct = start_pct + ((end_pct - start_pct) * (i + 1) / total_chunks)
            progress(progress_pct, desc=f"Analizuję fragment {i+1}/{total_chunks}...")

            graph = extractor.extract_knowledge(chunk, chunk_id=f"Part {i+1}")
            knowledge_base.append(graph.model_dump())

        # Zapis JSON
        base_name = os.path.basename(txt_file).replace('.txt', '')
        json_filename = f"{base_name}_kb.json"
        json_path = os.path.join(DATA_PROCESSED, json_filename)

        os.makedirs(DATA_PROCESSED, exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

        unload_model(MODEL_EXTRACTOR)

        return json_path

    except Exception as e:
        logger.error(f"Błąd ekstrakcji: {e}")
        return None


def process_youtube(
    url: str,
    language: str,
    model_size: str,
    output_format: str,
    do_transcribe: bool,
    do_extraction: bool,
    do_summarize: bool,
    download_subs: bool,
    summary_style: str,
    output_path: str,
    progress: gr.Progress = gr.Progress()
) -> Tuple[str, str, str]:
    """
    Przetwarza URL YouTube.

    Returns:
        (status_message, transcript_path, knowledge_base_path)
    """
    if not url or not url.strip():
        return "Błąd: Podaj URL YouTube", "", ""

    progress_tracker = GradioProgress(progress)
    stop_event = DummyStopEvent()
    processor = ContentProcessor(logger, stop_event, progress_tracker.update)

    lang_code = WHISPER_LANGUAGES.get(language, "pl")

    try:
        # 1. Pobieranie
        progress(0.05, desc="Pobieranie z YouTube...")
        downloaded = processor.download_video(url, output_path, "audio_only", "128")

        if not downloaded:
            return "Błąd: Nie udało się pobrać wideo", "", ""

        item = downloaded[0]
        audio_file = item.get('video')
        subtitle_path = item.get('subtitles')

        # 2. Transkrypcja
        txt_file = None
        json_file = None

        if download_subs and subtitle_path and os.path.exists(subtitle_path):
            progress(0.3, desc="Konwersja napisów...")
            txt_file = processor.convert_subtitles_to_txt(subtitle_path)
        elif do_transcribe:
            progress(0.2, desc=f"Transkrypcja ({model_size})...")
            segments, info = processor.transcribe_video(audio_file, lang_code, model_size)
            output_base = os.path.join(output_path, os.path.basename(audio_file))
            txt_file, json_file = processor.save_transcription(
                segments, info, output_base, output_format, lang_code
            )

        # Czyszczenie GPU po transkrypcji
        clear_gpu_memory()

        # 3. Ekstrakcja wiedzy
        kb_path = None
        if txt_file and do_extraction:
            progress(0.6, desc="Ekstrakcja wiedzy...")
            kb_path = run_knowledge_extraction_internal(txt_file, progress, 0.6, 0.95)

        # 4. Podsumowanie (opcjonalne)
        if txt_file and do_summarize:
            progress(0.95, desc="Generowanie podsumowania...")
            summary = processor.summarize_from_file(txt_file, style=summary_style)
            if summary:
                summary_path = os.path.splitext(txt_file)[0] + "_podsumowanie.txt"
                with open(summary_path, "w", encoding='utf-8') as f:
                    f.write(summary)

        progress(1.0, desc="Gotowe!")

        # Status
        status_parts = []
        if txt_file:
            status_parts.append(f"Transkrypcja: {os.path.basename(txt_file)}")
        if kb_path:
            status_parts.append(f"Baza wiedzy: {os.path.basename(kb_path)}")

        status = "\n".join(status_parts) if status_parts else "Zakończono bez wyników"

        return status, txt_file or "", kb_path or ""

    except Exception as e:
        return f"Błąd: {str(e)}", "", ""


def process_local_files(
    files: List,
    language: str,
    model_size: str,
    output_format: str,
    do_transcribe: bool,
    do_extraction: bool,
    do_summarize: bool,
    convert_to_mp3: bool,
    summary_style: str,
    output_path: str,
    progress: gr.Progress = gr.Progress()
) -> Tuple[str, str, str]:
    """
    Przetwarza pliki lokalne.

    Returns:
        (status_message, last_transcript_path, last_kb_path)
    """
    if not files:
        return "Błąd: Wybierz pliki", "", ""

    progress_tracker = GradioProgress(progress)
    stop_event = DummyStopEvent()
    processor = ContentProcessor(logger, stop_event, progress_tracker.update)

    lang_code = WHISPER_LANGUAGES.get(language, "pl")
    os.makedirs(output_path, exist_ok=True)

    results = []
    last_txt = ""
    last_kb = ""
    total_files = len(files)

    try:
        for idx, uploaded_file in enumerate(files):
            file_progress_start = idx / total_files
            file_progress_end = (idx + 1) / total_files

            # Gradio zwraca ścieżkę do pliku tymczasowego
            if hasattr(uploaded_file, 'name'):
                src_path = uploaded_file.name
                filename = os.path.basename(src_path)
            else:
                src_path = uploaded_file
                filename = os.path.basename(uploaded_file)

            progress(file_progress_start + 0.05, desc=f"Przetwarzanie {idx+1}/{total_files}: {filename}")

            # Kopiuj do output_path
            target_file = os.path.join(output_path, filename)
            if src_path != target_file:
                shutil.copy2(src_path, target_file)

            # Konwersja do MP3 (tylko dla plików audio/video, nie .txt)
            if convert_to_mp3 and not filename.lower().endswith(('.mp3', '.txt')):
                progress(file_progress_start + 0.1, desc=f"Konwersja do MP3: {filename}")
                mp3_path = os.path.join(output_path, os.path.splitext(filename)[0] + ".mp3")
                target_file = processor.convert_to_mp3(target_file, mp3_path)

            # Transkrypcja
            txt_file = None
            if filename.lower().endswith('.txt'):
                txt_file = target_file
                last_txt = txt_file
                logger.log(f"Plik .txt wykryty, pomijam transkrypcję dla {filename}")
            elif do_transcribe:
                pct = file_progress_start + 0.2
                progress(pct, desc=f"Transkrypcja ({model_size}): {filename}")
                segments, info = processor.transcribe_video(target_file, lang_code, model_size)
                output_base = os.path.join(output_path, os.path.basename(target_file))
                txt_file, json_file = processor.save_transcription(
                    segments, info, output_base, output_format, lang_code
                )
                last_txt = txt_file

            # Czyszczenie GPU
            clear_gpu_memory()

            # Ekstrakcja wiedzy
            if txt_file and do_extraction:
                pct = file_progress_start + 0.6
                progress(pct, desc=f"Ekstrakcja wiedzy: {filename}")
                kb_path = run_knowledge_extraction_internal(
                    txt_file, progress,
                    file_progress_start + 0.6,
                    file_progress_end - 0.05
                )
                if kb_path:
                    last_kb = kb_path

            # Podsumowanie
            if txt_file and do_summarize:
                pct = file_progress_end - 0.05
                progress(pct, desc=f"Podsumowanie: {filename}")
                summary = processor.summarize_from_file(txt_file, style=summary_style)
                if summary:
                    summary_path = os.path.splitext(txt_file)[0] + "_podsumowanie.txt"
                    with open(summary_path, "w", encoding='utf-8') as f:
                        f.write(summary)

            results.append(filename)

        progress(1.0, desc="Gotowe!")

        status = f"Przetworzono {len(results)} plik(ów):\n" + "\n".join(f"- {r}" for r in results)
        return status, last_txt, last_kb

    except Exception as e:
        return f"Błąd: {str(e)}", last_txt, last_kb


# =============================================================================
# SEKCJA 4: FUNKCJE TAB 2 - LABORATORIUM TEKSTU
# =============================================================================

def get_kb_files() -> List[str]:
    """Pobiera listę plików bazy wiedzy."""
    files = glob.glob(os.path.join(DATA_PROCESSED, "*_kb.json"))
    files.sort(key=os.path.getmtime, reverse=True)
    return files


def load_kb_file(filepath: str) -> Tuple[int, int, int, int, str, str]:
    """
    Ładuje plik bazy wiedzy i zwraca metryki.

    Returns:
        (segments, concepts, tools, tips, topics_str, preview_json)
    """
    if not filepath or not os.path.exists(filepath):
        return 0, 0, 0, 0, "", "{}"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        all_concepts = []
        all_tools = []
        all_tips = []
        all_topics = set()

        for item in data:
            if 'key_concepts' in item:
                all_concepts.extend(item['key_concepts'])
            if 'tools' in item:
                all_tools.extend(item['tools'])
            if 'tips' in item:
                all_tips.extend(item['tips'])
            if 'topics' in item:
                all_topics.update(item['topics'])

        topics_str = ", ".join(list(all_topics)[:15])

        # Podgląd (pierwsze 2 segmenty)
        preview = json.dumps(data[:2], ensure_ascii=False, indent=2) if data else "{}"

        return len(data), len(all_concepts), len(all_tools), len(all_tips), topics_str, preview

    except Exception as e:
        return 0, 0, 0, 0, f"Błąd: {e}", "{}"


def extract_topic_from_filename(filename: str) -> str:
    """Wyciąga czytelny temat z nazwy pliku."""
    import re
    topic = os.path.basename(filename)
    for suffix in ['.json', '.txt', '.mp4', '.mp3', '_transkrypcja', '_kb', '_podsumowanie']:
        topic = topic.replace(suffix, '')
    topic = topic.replace('_', ' ').replace('-', ' ')
    topic = re.sub(r'^\d{4}\s*\d{2}\s*\d{2}\s*', '', topic)
    return topic.strip().title()[:100]


def generate_note_streaming(
    selected_file: str,
    style: str,
    topic_name: str,
    custom_system_prompt: str,
    custom_user_prompt: str,
    source_url: str,
    source_title: str,
    duration: str,
    aliases: str
) -> Generator[str, None, None]:
    """
    Generator streamujący notatkę token po tokenie.
    """
    if not selected_file or not os.path.exists(selected_file):
        yield "Błąd: Wybierz plik bazy wiedzy"
        return

    if not topic_name.strip():
        topic_name = extract_topic_from_filename(selected_file)

    try:
        with open(selected_file, 'r', encoding='utf-8') as f:
            knowledge_data = json.load(f)

        writer = ReportWriter()

        # Przygotuj metadane
        metadata = {
            'source_url': source_url.strip() if source_url else '',
            'source_title': source_title.strip() if source_title else '',
            'duration': duration.strip() if duration else '',
            'aliases': [a.strip() for a in aliases.split(',') if a.strip()] if aliases else []
        }

        # Przygotuj kontekst
        context_str, tags_list = writer._prepare_context(knowledge_data)

        # Wybierz prompty
        template = PROMPT_TEMPLATES.get(style, PROMPT_TEMPLATES["standard"])
        system_prompt = custom_system_prompt.strip() if custom_system_prompt.strip() else template["system"]
        user_prompt_template = custom_user_prompt.strip() if custom_user_prompt.strip() else template["user"]
        final_user_prompt = user_prompt_template.replace("{topic_name}", topic_name).replace("{context_items}", context_str)

        # Generuj YAML header
        yaml_header = writer._build_frontmatter(topic_name, tags_list, style, metadata)
        yield yaml_header

        # Streaming content
        accumulated = yaml_header
        for token in writer.llm.generate_stream(system_prompt, final_user_prompt):
            accumulated += token
            yield accumulated

        # Source index
        source_index = writer._build_source_index(knowledge_data)
        yield accumulated + source_index

    except Exception as e:
        yield f"Błąd generowania: {str(e)}"


def save_note_locally(content: str, filename: str) -> str:
    """Zapisuje notatkę lokalnie."""
    if not content or not filename:
        return "Błąd: Brak treści lub nazwy pliku"

    try:
        os.makedirs(DATA_OUTPUT, exist_ok=True)
        filepath = os.path.join(DATA_OUTPUT, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Zapisano: {filepath}"
    except Exception as e:
        return f"Błąd zapisu: {e}"


def save_to_obsidian(content: str, filename: str, vault_path: str) -> str:
    """Kopiuje notatkę do Obsidian vault."""
    if not content or not content.strip():
        return "⚠️ **Brak treści do zapisania** - najpierw wygeneruj notatkę"
    if not filename:
        return "⚠️ **Brak nazwy pliku**"
    if not vault_path or not os.path.isdir(vault_path):
        return "⚠️ **Nieprawidłowa ścieżka do Obsidian** - sprawdź ustawienia"

    try:
        # Najpierw zapisz lokalnie
        os.makedirs(DATA_OUTPUT, exist_ok=True)
        local_path = os.path.join(DATA_OUTPUT, filename)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Kopiuj do Obsidian
        obsidian_path = os.path.join(vault_path, filename)
        shutil.copy2(local_path, obsidian_path)

        return f"✅ **Zapisano!** Plik: `{filename}`"
    except Exception as e:
        return f"❌ **Błąd:** {e}"


# =============================================================================
# SEKCJA 5: FUNKCJE TAB 3 - CLOUD BATCH
# =============================================================================

def run_batch_wizard(
    urls_text: str,
    whisper_model: str,
    progress: gr.Progress = gr.Progress()
) -> Tuple[str, str]:
    """
    Przetwarza listę URLi YouTube i wysyła do OpenAI Batch API.

    Returns:
        (log_output, batch_id_or_error)
    """
    urls = [u.strip() for u in urls_text.strip().split('\n')
            if u.strip() and not u.strip().startswith('#')]

    if not urls:
        return "Brak URLi do przetworzenia", ""

    logs = []
    def log(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] {msg}")

    stop_event = DummyStopEvent()

    def progress_callback(percent: float, stage: str = ""):
        progress(percent / 100.0, desc=stage)

    # Inicjalizacja komponentów
    simple_logger = SimpleLogger(log)

    downloader = Downloader(
        logger=simple_logger,
        stop_event=stop_event,
        progress_callback=progress_callback
    )

    transcriber = Transcriber(
        logger=simple_logger,
        stop_event=stop_event,
        progress_callback=progress_callback
    )

    os.makedirs(DATA_RAW, exist_ok=True)
    os.makedirs(DATA_PROCESSED, exist_ok=True)

    successful_requests = []
    failed_urls = []
    total_urls = len(urls)

    for i, url in enumerate(urls, 1):
        log(f"--- Przetwarzanie [{i}/{total_urls}] ---")

        try:
            # Pobieranie
            log(f"Pobieranie: {url[:60]}...")
            downloaded = downloader.download_video(
                url=url, save_path=DATA_RAW,
                quality="audio_only", audio_quality="128"
            )

            if not downloaded:
                log("Nie udało się pobrać")
                failed_urls.append(url)
                continue

            file_info = downloaded[0]
            audio_file = file_info["video"]
            source_title = file_info.get("source_title", f"video_{i}")

            if not os.path.exists(audio_file):
                log(f"Plik audio nie istnieje: {audio_file}")
                failed_urls.append(url)
                continue

            log(f"Pobrano: {os.path.basename(audio_file)}")

            # Transkrypcja
            log(f"Transkrypcja ({whisper_model})...")
            segments, info = transcriber.transcribe_video(
                filename=audio_file, language=None, model_size=whisper_model
            )

            output_file, _ = transcriber.save_transcription(
                segments, info, audio_file, "txt_no_timestamps", None
            )

            log(f"Zapisano: {os.path.basename(output_file)}")

            # Czyszczenie tekstu
            with open(output_file, "r", encoding="utf-8") as f:
                raw_text = f.read()
            cleaned_text = clean_transcript(raw_text)

            # Czyszczenie GPU
            clear_gpu_memory()

            # Podział na chunki i budowanie requestów
            base_custom_id = sanitize_filename(source_title)
            chunks = smart_split_text(cleaned_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)
            
            for chunk_index, chunk_content in enumerate(chunks):
                chunk_custom_id = f"{base_custom_id}__part_{chunk_index}"
                batch_request = build_batch_request(
                    custom_id=chunk_custom_id,
                    transcript_text=chunk_content,
                    model=MODEL_EXTRACTOR_OPENAI
                )

                successful_requests.append({
                    "request": batch_request,
                    "source_url": url,
                    "source_title": source_title,
                    "transcript_file": output_file
                })

            log(f"Przygotowano {len(chunks)} fragmentów dla: {base_custom_id}")

            # Cleanup audio
            try:
                os.remove(audio_file)
                log(f"Usunięto: {os.path.basename(audio_file)}")
            except:
                pass

        except Exception as e:
            log(f"BŁĄD: {e}")
            failed_urls.append(url)
            clear_gpu_memory()

        progress(i / total_urls, desc=f"Przetworzono {i}/{total_urls}")

    # Podsumowanie
    log(f"--- PODSUMOWANIE ---")
    log(f"Sukces: {len(successful_requests)}/{total_urls}")
    log(f"Błędy: {len(failed_urls)}/{total_urls}")

    # Wysyłanie do OpenAI
    if not successful_requests:
        return "\n".join(logs), "Brak poprawnych transkrypcji"

    try:
        batch_manager = BatchManager()
        requests_list = [r["request"] for r in successful_requests]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jsonl_filename = f"wizard_batch_{timestamp}.jsonl"
        jsonl_path = batch_manager.create_batch_file(requests_list, jsonl_filename)

        description = f"Batch Wizard {timestamp} - {len(requests_list)} transkrypcji"
        batch_id = batch_manager.upload_and_submit(jsonl_path, description=description)

        log(f"BATCH WYSŁANY! ID: {batch_id}")

        # Zapisz manifest
        manifest = {
            "batch_id": batch_id,
            "timestamp": timestamp,
            "total_urls": total_urls,
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

        manifest_path = os.path.join(DATA_PROCESSED, f"wizard_manifest_{timestamp}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        log(f"Manifest zapisany: {manifest_path}")

        return "\n".join(logs), batch_id

    except Exception as e:
        log(f"Błąd wysyłania: {e}")
        return "\n".join(logs), f"Błąd: {e}"


def list_batches() -> str:
    """Pobiera listę aktywnych batchy."""
    if not OPENAI_API_KEY:
        return "Brak klucza API OpenAI"

    try:
        bm = BatchManager()
        batches = bm.list_active_batches()

        if not batches:
            return "Brak aktywnych batchy"

        lines = []
        status_icons = {
            "completed": "OK",
            "failed": "FAIL",
            "in_progress": "...",
            "validating": "?",
            "expired": "EXP",
            "cancelling": "X",
            "cancelled": "X"
        }

        for b in batches:
            icon = status_icons.get(b.status, "?")
            dt = datetime.fromtimestamp(b.created_at).strftime('%Y-%m-%d %H:%M')
            desc = b.metadata.get("description", "Bez opisu") if b.metadata else "Bez opisu"
            lines.append(f"[{icon}] {dt} | {b.id[:20]}... | {desc}")

        return "\n".join(lines)

    except Exception as e:
        return f"Błąd: {e}"


def retrieve_batch_results(batch_id: str) -> Tuple[str, str]:
    """
    Pobiera wyniki batcha.

    Returns:
        (status_message, json_results)
    """
    if not batch_id or not batch_id.strip():
        return "Podaj Batch ID", ""

    try:
        bm = BatchManager()
        results = bm.retrieve_results(batch_id.strip())

        if not results:
            return "Brak wyników lub batch nie jest ukończony", ""

        json_str = json.dumps(results, ensure_ascii=False, indent=2)
        return f"Pobrano {len(results)} wyników", json_str

    except Exception as e:
        return f"Błąd: {e}", ""


def import_batch_to_lab(batch_id: str) -> str:
    """Importuje wyniki batcha do Laboratorium."""
    if not batch_id or not batch_id.strip():
        return "Podaj Batch ID"

    try:
        bm = BatchManager()
        results = bm.retrieve_results(batch_id.strip())

        if not results:
            return "Brak wyników do importu"

        imported = bm.import_batch_to_lab(results)

        if imported:
            return f"Zaimportowano {len(imported)} plików:\n" + "\n".join(f"- {f}" for f in imported)
        else:
            return "Błąd podczas importu"

    except Exception as e:
        return f"Błąd: {e}"


def submit_batch_files(selected_files: List[str]) -> str:
    """Wysyła wybrane pliki do OpenAI Batch API."""
    if not selected_files:
        return "Wybierz pliki"

    if not OPENAI_API_KEY:
        return "Brak klucza API OpenAI"

    try:
        all_reqs = []
        for f_path in selected_files:
            with open(f_path, "r", encoding="utf-8") as f:
                text = f.read()

            base_custom_id = os.path.basename(f_path)
            # Używamy smart_split_text zamiast prostego text[:15000]
            chunks = smart_split_text(text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)
            
            for chunk_index, chunk_content in enumerate(chunks):
                chunk_custom_id = f"{base_custom_id}__part_{chunk_index}"
                req = build_batch_request(
                    custom_id=chunk_custom_id,
                    transcript_text=chunk_content,
                    model=MODEL_EXTRACTOR_OPENAI
                )
                all_reqs.append(req)

        bm = BatchManager()
        import time
        batch_file_path = bm.create_batch_file(all_reqs, f"batch_{int(time.time())}.jsonl")
        batch_id = bm.upload_and_submit(batch_file_path, f"Analiza {len(selected_files)} plików")

        return f"Zadanie wysłane! Batch ID: {batch_id}"

    except Exception as e:
        return f"Błąd: {e}"


# =============================================================================
# SEKCJA 6: BUDOWA INTERFEJSU
# =============================================================================

def create_app() -> gr.Blocks:
    """Tworzy kompletną aplikację Gradio."""

    # Wykrycie GPU
    gpu_info = ""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        gpu_info = f"GPU: {gpu_name} ({vram_gb:.1f} GB)"
    else:
        gpu_info = "CPU Mode - będzie wolno!"

    # Sprawdzenie FFmpeg
    ffmpeg_ok, _ = check_ffmpeg()

    # Opisy stylów
    style_descriptions = {
        "standard": "Zbalansowany, edukacyjny. TL;DR na górze, Wikilinks [[Termin]], krótkie akapity.",
        "academic": "Formalny, analityczny. Pełne akapity prozy, głęboka analiza, bogate słownictwo.",
        "blog": "Luźny, bezpośredni. Emotikony, chwytliwe nagłówki, storytelling."
    }

    with gr.Blocks(
        title="AI Transkrypcja & Notatki v2.0",
        theme=gr.themes.Soft(),
    ) as app:

        gr.Markdown("# AI Transkrypcja & Notatki v2.0")

        with gr.Row():
            # === SIDEBAR ===
            with gr.Column(scale=1):
                gr.Markdown("## Konfiguracja")

                # Status sprzętu
                gr.Markdown(f"**{gpu_info}**")

                gr.Markdown("---")

                # Język - widoczny zawsze bo ważny
                language_dropdown = gr.Dropdown(
                    choices=list(WHISPER_LANGUAGES.keys()),
                    value="Polski",
                    label="Język nagrania"
                )

                # Ustawienia AI - domyślnie ukryte
                with gr.Accordion("Ustawienia AI", open=False):
                    model_dropdown = gr.Dropdown(
                        choices=WHISPER_MODELS,
                        value=DEFAULT_MODEL_SIZE,
                        label="Model rozpoznawania mowy",
                        info="large-v3 = lepsza jakość, medium = szybszy"
                    )

                    llm_provider_radio = gr.Radio(
                        choices=["ollama", "openai"],
                        value=LLM_PROVIDER,
                        label="Silnik AI",
                        info="ollama = lokalny (darmowy), openai = chmura (płatny)"
                    )

                gr.Markdown("---")

                # Zadania
                gr.Markdown("### Co zrobić?")
                do_transcribe_cb = gr.Checkbox(value=True, label="Zamień mowę na tekst")
                do_extraction_cb = gr.Checkbox(value=True, label="Przeanalizuj treść (dla notatek)")
                do_summarize_cb = gr.Checkbox(value=False, label="Wygeneruj krótkie podsumowanie")

                gr.Markdown("---")

                # Wyjście - uproszczone
                output_path_input = gr.Textbox(
                    value=os.path.abspath(DATA_OUTPUT),
                    label="Folder zapisu",
                    visible=False  # ukryty - używamy domyślnego
                )

                # Opcje zaawansowane - wszystko co techniczne
                with gr.Accordion("Opcje zaawansowane", open=False):
                    output_format_dropdown = gr.Dropdown(
                        choices=["json", "txt", "txt_no_timestamps", "srt", "vtt"],
                        value="json",
                        label="Format transkrypcji",
                        info="json = z metadanymi, txt = czysty tekst"
                    )
                    download_subs_cb = gr.Checkbox(value=True, label="Pobierz napisy YT")
                    summary_style_dropdown = gr.Dropdown(
                        choices=["Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe"],
                        value="Zwięzłe (3 punkty)",
                        label="Styl podsumowania"
                    )
                    # Domyślna ścieżka Obsidian z konfiguracji
                    default_obsidian = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_SUBFOLDER) if OBSIDIAN_EXPORT_ENABLED else ""
                    obsidian_vault_input = gr.Textbox(
                        value=default_obsidian,
                        label="Vault Obsidian",
                        placeholder="/path/to/vault"
                    )

                    clear_vram_btn = gr.Button("Zwolnij VRAM", variant="secondary")

                # Status FFmpeg
                gr.Markdown("---")
                if ffmpeg_ok:
                    gr.Markdown("FFmpeg: OK")
                else:
                    gr.Markdown("**FFmpeg: BRAK**")

            # === MAIN CONTENT ===
            with gr.Column(scale=4):
                with gr.Tabs() as tabs:

                    # === TAB 1: Przetwarzanie Audio ===
                    with gr.Tab("Nowa Transkrypcja", id="tab_transcribe"):
                        gr.Markdown("## Zamień nagranie na tekst")
                        gr.Markdown("*Wklej link YouTube lub wgraj plik audio/wideo*")

                        with gr.Row():
                            # YouTube
                            with gr.Column():
                                gr.Markdown("### Z YouTube")
                                yt_url_input = gr.Textbox(
                                    label="Link",
                                    placeholder="https://www.youtube.com/watch?v=..."
                                )
                                start_yt_btn = gr.Button("Rozpocznij", variant="primary")

                            # Plik lokalny
                            with gr.Column():
                                gr.Markdown("### Z pliku")
                                file_upload = gr.File(
                                    label="Wybierz pliki audio/video lub .txt",
                                    file_types=[".mp4", ".mp3", ".m4a", ".wav", ".mkv", ".avi", ".txt"],
                                    file_count="multiple"
                                )
                                convert_mp3_cb = gr.Checkbox(value=True, label="Konwertuj na MP3", visible=False)
                                start_local_btn = gr.Button("Rozpocznij", variant="primary")

                        gr.Markdown("---")

                        # Wyniki
                        status_output = gr.Markdown("*Wklej link lub wybierz plik aby rozpocząć*")

                        # Ukryte pola ze ścieżkami (techniczne)
                        with gr.Row(visible=False):
                            transcript_output = gr.Textbox(label="Ścieżka transkrypcji", interactive=False)
                            kb_output = gr.Textbox(label="Ścieżka bazy wiedzy", interactive=False)

                        # Przycisk do tworzenia notatki - główna akcja po transkrypcji
                        with gr.Row():
                            create_note_btn = gr.Button(
                                "Stwórz notatkę z tej transkrypcji",
                                variant="secondary",
                                visible=False,
                                size="lg"
                            )

                    # === TAB 2: Stwórz Notatkę ===
                    with gr.Tab("Stwórz Notatkę", id="tab_notes"):
                        gr.Markdown("## Wygeneruj notatkę z transkrypcji")

                        # Wybór źródła - prosty dropdown
                        with gr.Row():
                            kb_file_dropdown = gr.Dropdown(
                                choices=get_kb_files(),
                                label="Wybierz transkrypcję",
                                interactive=True,
                                scale=4
                            )
                            refresh_files_btn = gr.Button("🔄", scale=1, min_width=50)

                        # Status generowania - WIDOCZNY FEEDBACK
                        generation_status = gr.Markdown("", elem_id="generation-status")

                        # Opcje dostosowania - ukryte domyślnie
                        with gr.Accordion("Dostosuj notatkę (opcjonalne)", open=False):
                            # Temat notatki
                            topic_input = gr.Textbox(
                                label="Temat notatki",
                                placeholder="Zostaw puste = automatyczny z nazwy pliku",
                                info="Opcjonalne - domyślnie użyje nazwy pliku"
                            )

                            # Styl
                            saved_style, custom_sys_init, custom_usr_init = load_custom_settings()
                            style_radio = gr.Radio(
                                choices=["standard", "academic", "blog"],
                                value=saved_style,
                                label="Styl",
                                info="standard = przejrzysty | academic = formalny | blog = luźny"
                            )
                            style_description = gr.Markdown(f"*{style_descriptions[saved_style]}*")

                        # Ukryte pola dla zaawansowanych opcji (domyślne wartości)
                        with gr.Row(visible=False):
                            source_url_input = gr.Textbox(value="")
                            source_title_input = gr.Textbox(value="")
                            duration_input = gr.Textbox(value="")
                            aliases_input = gr.Textbox(value="")
                            system_prompt_input = gr.Textbox(value=custom_sys_init or PROMPT_TEMPLATES["standard"]["system"])
                            user_prompt_input = gr.Textbox(value=custom_usr_init or PROMPT_TEMPLATES["standard"]["user"])

                        # Opcje zaawansowane - głęboko ukryte
                        with gr.Accordion("Opcje zaawansowane", open=False):
                            # Metryki źródła
                            gr.Markdown("**Statystyki źródła:**")
                            with gr.Row():
                                segments_metric = gr.Number(label="Segmenty", interactive=False)
                                concepts_metric = gr.Number(label="Pojęcia", interactive=False)
                                tools_metric = gr.Number(label="Narzędzia", interactive=False)
                                tips_metric = gr.Number(label="Wskazówki", interactive=False)
                            topics_display = gr.Textbox(label="Wykryte tematy", interactive=False)

                            gr.Markdown("---")

                            # Metadane dla Obsidian
                            gr.Markdown("**Metadane (dla Obsidian):**")
                            with gr.Row():
                                adv_source_url = gr.Textbox(label="URL źródła", placeholder="https://...")
                                adv_source_title = gr.Textbox(label="Tytuł źródła")
                            with gr.Row():
                                adv_duration = gr.Textbox(label="Czas trwania", placeholder="1:30:00")
                                adv_aliases = gr.Textbox(label="Tagi (przecinek)", placeholder="OSINT, Techniki")

                            gr.Markdown("---")

                            # Edycja promptów
                            gr.Markdown("**Edycja promptów AI:**")
                            use_custom_prompts_cb = gr.Checkbox(
                                label="Użyj własnych promptów i stylu (blokuje nadpisywanie przez style)",
                                value=bool(custom_sys_init)
                            )
                            with gr.Row():
                                save_settings_btn = gr.Button("💾 Zapisz te ustawienia jako domyślne", variant="secondary")
                                reset_prompts_btn = gr.Button("Przywróć domyślne dla stylu")

                            adv_system_prompt = gr.Textbox(
                                label="System Prompt",
                                lines=6,
                                value=custom_sys_init or PROMPT_TEMPLATES["standard"]["system"]
                            )
                            adv_user_prompt = gr.Textbox(
                                label="User Prompt",
                                lines=4,
                                value=custom_usr_init or PROMPT_TEMPLATES["standard"]["user"]
                            )

                            prompt_status = gr.Markdown("")

                            # Podgląd surowych danych
                            with gr.Accordion("Podgląd surowych danych (JSON)", open=False):
                                kb_preview = gr.Code(label="JSON", language="json")

                        # PRZYCISK GENEROWANIA - TERAZ POD USTAWIENIAMI
                        generate_btn = gr.Button("▶ Generuj Notatkę", variant="primary", size="lg")

                        # Wynik - podgląd jako domyślny widok
                        gr.Markdown("### Wygenerowana notatka")
                        preview_output = gr.Markdown()

                        # Zapis - GŁÓWNA AKCJA
                        with gr.Row():
                            output_filename_input = gr.Textbox(
                                label="Nazwa pliku",
                                value="notatka.md",
                                scale=3
                            )
                            # Nowy, główny przycisk Zapisz
                            save_all_btn = gr.Button("💾 Zapisz Notatkę", variant="primary", size="lg", scale=2)
                            to_obsidian_btn = gr.Button("🏔️ Wyślij do Obsidian", variant="secondary", size="lg", scale=2)

                        save_status = gr.Markdown("")

                        # Dodatkowe opcje zapisu
                        with gr.Accordion("Więcej opcji zapisu", open=False):
                            edit_output = gr.Textbox(label="Edytuj tekst przed zapisem", lines=15)
                            with gr.Row():
                                save_local_btn = gr.Button("Zapisz lokalnie", variant="secondary")
                                download_btn = gr.DownloadButton(label="Pobierz plik", variant="secondary")
                                clear_result_btn = gr.Button("Wyczyść", variant="stop")

                    # === TAB 3: Przetwarzanie Zbiorcze ===
                    with gr.Tab("Przetwarzanie Zbiorcze"):
                        gr.Markdown("## Przetwórz wiele filmów naraz")
                        gr.Markdown("*Idealne do przetwarzania całych playlist lub wielu filmów w tle*")

                        if not OPENAI_API_KEY:
                            gr.Markdown("**Skonfiguruj klucz API OpenAI w zmiennych środowiskowych!**")

                        # Batch Wizard - główna funkcja
                        gr.Markdown("### Wklej linki YouTube")
                        gr.Markdown("*System automatycznie pobierze, przetworzy i przygotuje notatki dla wszystkich filmów*")

                        wizard_urls_input = gr.Textbox(
                            label="Linki (jeden na linię)",
                            lines=6,
                            placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=..."
                        )

                        with gr.Row():
                            urls_count = gr.Number(label="Liczba filmów", interactive=False)
                            wizard_start_btn = gr.Button("Rozpocznij przetwarzanie", variant="primary", scale=2)

                        wizard_log_output = gr.Textbox(label="Postęp", lines=8, interactive=False)
                        wizard_result_output = gr.Textbox(label="ID zadania", interactive=False, visible=False)

                        # Opcje zaawansowane
                        with gr.Accordion("Opcje zaawansowane", open=False):
                            wizard_model_dropdown = gr.Dropdown(
                                choices=WHISPER_MODELS,
                                value=DEFAULT_MODEL_SIZE,
                                label="Model rozpoznawania mowy"
                            )

                            gr.Markdown("---")
                            gr.Markdown("**Przetwarzanie istniejących plików:**")

                            batch_files_select = gr.Dropdown(
                                choices=glob.glob(os.path.join(DATA_OUTPUT, "*.txt")),
                                label="Wybierz pliki tekstowe",
                                multiselect=True
                            )

                            with gr.Row():
                                refresh_batch_files_btn = gr.Button("Odśwież listę")
                                submit_batch_btn = gr.Button("Przetwórz wybrane pliki")

                            batch_submit_status = gr.Markdown("")

                            gr.Markdown("---")
                            gr.Markdown("**Historia zadań:**")
                            refresh_batches_btn = gr.Button("Odśwież historię")
                            batches_output = gr.Textbox(label="Zadania", lines=6, interactive=False)

                            gr.Markdown("---")
                            gr.Markdown("**Pobierz wyniki:**")
                            with gr.Row():
                                batch_id_input = gr.Textbox(label="ID zadania", placeholder="batch_...")
                                retrieve_btn = gr.Button("Pobierz")
                                import_btn = gr.Button("Importuj notatki")

                            retrieve_status = gr.Markdown("")
                            retrieve_results_output = gr.Code(label="Wyniki JSON", language="json")

        # =================================================================
        # EVENT HANDLERS
        # =================================================================

        # Sidebar: Zwolnij VRAM
        def clear_vram():
            unload_model(MODEL_EXTRACTOR)
            clear_gpu_memory()
            return "VRAM zwolniony"

        clear_vram_btn.click(fn=clear_vram, outputs=[])

        # Funkcja pokazująca przycisk po transkrypcji
        def show_create_note_btn(kb_path):
            """Pokaż przycisk 'Stwórz notatkę' jeśli mamy bazę wiedzy."""
            if kb_path and os.path.exists(kb_path):
                return gr.update(visible=True)
            return gr.update(visible=False)

        # Tab 1: Przetwarzanie YouTube
        start_yt_btn.click(
            fn=process_youtube,
            inputs=[
                yt_url_input, language_dropdown, model_dropdown, output_format_dropdown,
                do_transcribe_cb, do_extraction_cb, do_summarize_cb,
                download_subs_cb, summary_style_dropdown, output_path_input
            ],
            outputs=[status_output, transcript_output, kb_output]
        ).then(
            fn=show_create_note_btn,
            inputs=[kb_output],
            outputs=[create_note_btn]
        )

        # Tab 1: Przetwarzanie plików lokalnych
        start_local_btn.click(
            fn=process_local_files,
            inputs=[
                file_upload, language_dropdown, model_dropdown, output_format_dropdown,
                do_transcribe_cb, do_extraction_cb, do_summarize_cb,
                convert_mp3_cb, summary_style_dropdown, output_path_input
            ],
            outputs=[status_output, transcript_output, kb_output]
        ).then(
            fn=show_create_note_btn,
            inputs=[kb_output],
            outputs=[create_note_btn]
        )

        # Tab 1: Przycisk "Stwórz notatkę" - przenosi do Tab 2 z wybranym plikiem
        def go_to_notes_tab(kb_path):
            """Przejdź do Tab 2 i wybierz plik."""
            files = get_kb_files()
            selected = kb_path if kb_path and kb_path in files else (files[0] if files else None)
            # Załaduj metryki
            if selected:
                metrics = load_kb_file(selected)
                topic = extract_topic_from_filename(selected)
                return (
                    gr.update(choices=files, value=selected),  # kb_file_dropdown
                    gr.Tabs(selected="tab_notes"),             # tabs - przełącz na Tab 2
                    topic,                                     # topic_input
                    *metrics                                   # metryki
                )
            return (
                gr.update(choices=files),
                gr.Tabs(selected="tab_notes"),
                "",
                0, 0, 0, 0, "", "{}"
            )

        create_note_btn.click(
            fn=go_to_notes_tab,
            inputs=[kb_output],
            outputs=[kb_file_dropdown, tabs, topic_input, segments_metric, concepts_metric, tools_metric, tips_metric, topics_display, kb_preview]
        )

        # Tab 2: Odśwież listę plików KB
        refresh_files_btn.click(
            fn=lambda: gr.update(choices=get_kb_files()),
            outputs=[kb_file_dropdown]
        )

        # Tab 2: Załaduj plik KB
        kb_file_dropdown.change(
            fn=load_kb_file,
            inputs=[kb_file_dropdown],
            outputs=[segments_metric, concepts_metric, tools_metric, tips_metric, topics_display, kb_preview]
        )

        # Tab 2: Aktualizuj opis stylu
        def update_style_desc(style, use_custom):
            desc = style_descriptions.get(style, "")
            if use_custom:
                # Jeśli używamy własnych promptów, zwracamy tylko opis stylu, zachowując obecne prompty
                return f"*{desc}*", gr.update(), gr.update()
            
            template = PROMPT_TEMPLATES.get(style, PROMPT_TEMPLATES["standard"])
            return f"*{desc}*", template["system"], template["user"]

        style_radio.change(
            fn=update_style_desc,
            inputs=[style_radio, use_custom_prompts_cb],
            outputs=[style_description, adv_system_prompt, adv_user_prompt]
        )

        # Tab 2: Reset promptów
        def reset_prompts(style):
            template = PROMPT_TEMPLATES.get(style, PROMPT_TEMPLATES["standard"])
            return template["system"], template["user"]

        reset_prompts_btn.click(
            fn=reset_prompts,
            inputs=[style_radio],
            outputs=[adv_system_prompt, adv_user_prompt]
        )

        save_settings_btn.click(
            fn=save_custom_settings,
            inputs=[style_radio, adv_system_prompt, adv_user_prompt],
            outputs=[prompt_status]
        )

        # Tab 2: Generowanie notatki ze streamingiem
        def start_generation():
            """Pokazuje status 'Generuję...' i blokuje przycisk."""
            return (
                "⏳ **Generuję notatkę...** (może potrwać 1-2 minuty)",
                gr.update(interactive=False, value="⏳ Generuję...")
            )

        def finish_generation(content):
            """Ukrywa status i odblokowuje przycisk."""
            return (
                "",  # Ukryj status
                gr.update(interactive=True, value="▶ Generuj Notatkę"),
                content  # Kopiuj do edycji
            )

        generate_btn.click(
            fn=start_generation,
            outputs=[generation_status, generate_btn]
        ).then(
            fn=generate_note_streaming,
            inputs=[
                kb_file_dropdown, style_radio, topic_input,
                adv_system_prompt, adv_user_prompt,
                adv_source_url, adv_source_title, adv_duration, adv_aliases
            ],
            outputs=[preview_output]
        ).then(
            fn=finish_generation,
            inputs=[preview_output],
            outputs=[generation_status, generate_btn, edit_output]
        )

        # Tab 2: Aktualizuj nazwę pliku na podstawie KB
        def update_filename(kb_path, style):
            if kb_path:
                base = os.path.basename(kb_path).replace("_kb.json", "")
                return f"{base}_{style}.md"
            return "notatka.md"

        kb_file_dropdown.change(
            fn=update_filename,
            inputs=[kb_file_dropdown, style_radio],
            outputs=[output_filename_input]
        )

        style_radio.change(
            fn=update_filename,
            inputs=[kb_file_dropdown, style_radio],
            outputs=[output_filename_input]
        )

        # Tab 2: Zapisz lokalnie
        save_local_btn.click(
            fn=save_note_locally,
            inputs=[edit_output, output_filename_input],
            outputs=[save_status]
        )

        # Tab 2: Przygotuj plik do pobrania
        def prepare_download(content, filename):
            if not content:
                return None
            # Zapisz do pliku tymczasowego i zwróć ścieżkę
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(content)
                return f.name

        edit_output.change(
            fn=prepare_download,
            inputs=[edit_output, output_filename_input],
            outputs=[download_btn]
        )

        # Tab 2: Do Obsidian - używa preview_output (główny wynik)
        def save_obsidian_from_preview(preview_content, edit_content, filename, vault):
            """Zapisz do Obsidian - preferuj edytowany tekst, fallback na preview."""
            content = edit_content.strip() if edit_content and edit_content.strip() else preview_content
            return save_to_obsidian(content, filename, vault)

        to_obsidian_btn.click(
            fn=save_obsidian_from_preview,
            inputs=[preview_output, edit_output, output_filename_input, obsidian_vault_input],
            outputs=[save_status]
        )

        # Tab 2: Główny przycisk Zapisz - inteligentny wybór
        def smart_save(preview_content, edit_content, filename, vault):
            """Zapisuje do Obsidian jeśli dostępny, w przeciwnym razie lokalnie."""
            content = edit_content.strip() if edit_content and edit_content.strip() else preview_content
            if vault and os.path.exists(vault):
                return save_to_obsidian(content, filename, vault)
            else:
                return save_note_locally(content, filename)

        save_all_btn.click(
            fn=smart_save,
            inputs=[preview_output, edit_output, output_filename_input, obsidian_vault_input],
            outputs=[save_status]
        )

        # Tab 2: Wyczyść
        clear_result_btn.click(
            fn=lambda: ("", ""),
            outputs=[preview_output, edit_output]
        )

        # Tab 3: Liczenie URLi
        def count_urls(text):
            if not text:
                return 0
            lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#')]
            return len(lines)

        wizard_urls_input.change(
            fn=count_urls,
            inputs=[wizard_urls_input],
            outputs=[urls_count]
        )

        # Tab 3: Batch Wizard
        wizard_start_btn.click(
            fn=run_batch_wizard,
            inputs=[wizard_urls_input, wizard_model_dropdown],
            outputs=[wizard_log_output, wizard_result_output]
        )

        # Tab 3: Odśwież listę plików do batcha
        refresh_batch_files_btn.click(
            fn=lambda: gr.update(choices=glob.glob(os.path.join(DATA_OUTPUT, "*.txt"))),
            outputs=[batch_files_select]
        )

        # Tab 3: Wyślij batch
        submit_batch_btn.click(
            fn=submit_batch_files,
            inputs=[batch_files_select],
            outputs=[batch_submit_status]
        )

        # Tab 3: Odśwież listę batchy
        refresh_batches_btn.click(
            fn=list_batches,
            outputs=[batches_output]
        )

        # Tab 3: Pobierz wyniki
        retrieve_btn.click(
            fn=retrieve_batch_results,
            inputs=[batch_id_input],
            outputs=[retrieve_status, retrieve_results_output]
        )

        # Tab 3: Import do laboratorium
        import_btn.click(
            fn=import_batch_to_lab,
            inputs=[batch_id_input],
            outputs=[retrieve_status]
        )

    return app


# =============================================================================
# SEKCJA 7: MAIN
# =============================================================================

def main():
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main()
