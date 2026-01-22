"""
Handlery operacji dla Gradio UI.
Zawiera całą logikę biznesową połączoną z backendem.
"""

import os
import json
import re
from datetime import datetime
from typing import Generator, Optional, List, Dict, Any, Tuple
from pathlib import Path

import gradio as gr

from src.gui.adapters import (
    GradioProgressAdapter,
    LogCapture,
    get_stop_event,
    reset_cancel,
    create_progress_adapter,
)
from src.gui.constants import (
    STYLE_MAP,
    OUTPUT_FORMAT_MAP,
    format_error,
    format_success,
    LABELS,
)


# =============================================================================
# UTILITY HANDLERS
# =============================================================================

def get_system_status() -> Tuple[str, str]:
    """
    Pobiera status systemu dla sidebar.

    Returns:
        tuple: (gpu_info_markdown, ffmpeg_status_markdown)
    """
    # GPU Info
    try:
        from src.core.gpu_manager import get_gpu_memory_info
        info = get_gpu_memory_info()
        if info.get("device_name"):
            gpu_md = f"**GPU:** {info['device_name']}\n"
            gpu_md += f"**VRAM:** {info.get('free_gb', 0):.1f} / {info.get('total_gb', 0):.1f} GB wolne"
        else:
            gpu_md = "**GPU:** Niedostepne (tryb CPU)"
    except Exception:
        gpu_md = "**GPU:** Niedostepne (tryb CPU)"

    # FFmpeg
    try:
        from src.utils.helpers import check_ffmpeg
        ffmpeg_ok = check_ffmpeg()
        ffmpeg_md = "**FFmpeg:** OK" if ffmpeg_ok else "**FFmpeg:** BRAK - wymagany do konwersji"
    except Exception:
        ffmpeg_md = "**FFmpeg:** Nieznany status"

    return gpu_md, ffmpeg_md


def clear_vram() -> str:
    """
    Zwalnia pamięć VRAM.

    Returns:
        Komunikat statusu
    """
    try:
        from src.core.gpu_manager import clear_gpu_memory, get_gpu_memory_info
        from src.core.llm_engine import unload_model
        from src.utils.config import MODEL_EXTRACTOR, MODEL_WRITER, MODEL_TAGGER

        # Wyładuj wszystkie modele
        for model in [MODEL_EXTRACTOR, MODEL_WRITER, MODEL_TAGGER]:
            try:
                unload_model(model)
            except Exception:
                pass

        clear_gpu_memory(verbose=False)

        info = get_gpu_memory_info()
        if info.get("device_name"):
            return format_success(
                "vram_cleared",
                free_gb=info.get('free_gb', 0),
                total_gb=info.get('total_gb', 0)
            )
        return "VRAM zwolniony (tryb CPU)"
    except Exception as e:
        return f"Blad zwalniania VRAM: {str(e)}"


def check_ollama_status() -> str:
    """Sprawdza czy Ollama jest dostępna."""
    try:
        import requests
        from src.utils.config import OLLAMA_URL
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return "Ollama: OK"
        return "Ollama: Blad polaczenia"
    except Exception:
        return "Ollama: Niedostepna"


# =============================================================================
# TAB 1: TRANSCRIPTION HANDLERS
# =============================================================================

def validate_youtube_url(url: str) -> Tuple[bool, str]:
    """Waliduje URL YouTube."""
    if not url or not url.strip():
        return False, format_error("no_url")

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False, format_error("invalid_url")

    return True, ""


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
) -> Generator[Tuple[str, str, str], None, None]:
    """
    Przetwarza URL YouTube z real-time progress.

    Jest to GENERATOR dla Gradio streaming.

    Yields:
        tuple: (status_message, transcript_path, kb_path)
    """
    from src.utils.config import WHISPER_LANGUAGES, DATA_OUTPUT

    # Reset cancel flag
    reset_cancel()
    stop_event = get_stop_event()

    # Walidacja
    valid, error = validate_youtube_url(url)
    if not valid:
        yield error, "", ""
        return

    # Przygotowanie
    log_capture = LogCapture()
    progress_adapter = GradioProgressAdapter(progress)

    # Mapowanie języka
    lang_code = WHISPER_LANGUAGES.get(language, "pl")
    output_dir = output_path if output_path else DATA_OUTPUT

    try:
        from src.core.processor import Processor

        processor = Processor(
            logger=log_capture,
            stop_event=stop_event,
            progress_callback=progress_adapter.update
        )

        # 1. Pobieranie
        log_capture.log("Rozpoczynam pobieranie z YouTube...")
        yield log_capture.get_logs(), "", ""

        downloaded = processor.download_video(url, output_dir, "bestaudio", "192")

        if stop_event.is_set():
            yield format_error("cancelled"), "", ""
            return

        if not downloaded:
            yield format_error("download_failed", "Brak wynikow pobierania"), "", ""
            return

        item = downloaded[0]
        audio_file = item.get('video') or item.get('audio')
        subtitle_path = item.get('subtitles')

        log_capture.log(f"Pobrano: {os.path.basename(audio_file)}")
        yield log_capture.get_logs(), "", ""

        # 2. Transkrypcja
        txt_file = None
        json_file = None

        if download_subs and subtitle_path and os.path.exists(subtitle_path):
            log_capture.log("Konwertowanie napisow YouTube...")
            txt_file = processor.convert_subtitles_to_txt(subtitle_path)
            yield log_capture.get_logs(), txt_file or "", ""

        elif do_transcribe:
            log_capture.log(f"Rozpoczynam transkrypcje Whisper ({model_size})...")
            yield log_capture.get_logs(), "", ""

            segments, info = processor.transcribe_video(audio_file, lang_code, model_size)

            if stop_event.is_set():
                yield format_error("cancelled"), "", ""
                return

            # Zapis
            output_fmt = OUTPUT_FORMAT_MAP.get(output_format, "json")
            txt_file, json_file = processor.save_transcription(
                segments, info, audio_file, output_fmt, lang_code
            )

            log_capture.log(f"Transkrypcja zapisana: {os.path.basename(txt_file)}")
            yield log_capture.get_logs(), txt_file or "", ""

            # Czyszczenie GPU
            from src.core.gpu_manager import clear_gpu_memory
            clear_gpu_memory()

        # 3. Ekstrakcja wiedzy
        kb_path = ""
        if do_extraction and txt_file:
            log_capture.log("Rozpoczynam ekstrakcje wiedzy...")
            yield log_capture.get_logs(), txt_file, ""

            kb_path = run_knowledge_extraction(txt_file, progress_adapter, log_capture)

            if stop_event.is_set():
                yield format_error("cancelled"), txt_file, ""
                return

            if kb_path:
                log_capture.log(f"Baza wiedzy: {os.path.basename(kb_path)}")

        # 4. Podsumowanie (opcjonalne)
        if do_summarize and txt_file:
            log_capture.log("Generowanie podsumowania...")
            yield log_capture.get_logs(), txt_file, kb_path

            try:
                summary = processor.summarize_from_file(txt_file, style=summary_style)
                log_capture.log("Podsumowanie wygenerowane")
            except Exception as e:
                log_capture.warning(f"Blad podsumowania: {e}")

        # Finalizacja
        log_capture.log("Przetwarzanie zakonczone!")
        yield log_capture.get_logs(), txt_file or "", kb_path or ""

    except Exception as e:
        log_capture.error(str(e))
        yield log_capture.get_logs() + f"\n\n{format_error('download_failed', str(e))}", "", ""


def process_local_files(
    files: List[Any],
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
) -> Generator[Tuple[str, str, str], None, None]:
    """
    Przetwarza lokalne pliki audio/video.

    Yields:
        tuple: (status_message, transcript_path, kb_path)
    """
    from src.utils.config import WHISPER_LANGUAGES, DATA_OUTPUT

    reset_cancel()
    stop_event = get_stop_event()

    if not files:
        yield format_error("no_file"), "", ""
        return

    log_capture = LogCapture()
    progress_adapter = GradioProgressAdapter(progress)

    lang_code = WHISPER_LANGUAGES.get(language, "pl")
    output_dir = output_path if output_path else DATA_OUTPUT

    try:
        from src.core.processor import Processor
        from src.core.gpu_manager import clear_gpu_memory

        processor = Processor(
            logger=log_capture,
            stop_event=stop_event,
            progress_callback=progress_adapter.update
        )

        all_transcripts = []
        all_kb_paths = []

        for i, file_obj in enumerate(files):
            if stop_event.is_set():
                yield format_error("cancelled"), "", ""
                return

            # Pobierz ścieżkę pliku
            file_path = file_obj.name if hasattr(file_obj, 'name') else str(file_obj)
            filename = os.path.basename(file_path)

            log_capture.log(f"Przetwarzanie pliku {i+1}/{len(files)}: {filename}")
            yield log_capture.get_logs(), "", ""

            # Konwersja do MP3 (opcjonalna)
            if convert_to_mp3 and not file_path.endswith('.mp3'):
                log_capture.log("Konwertowanie do MP3...")
                file_path = processor.convert_to_mp3(file_path)

            # Transkrypcja
            txt_file = None
            if do_transcribe:
                log_capture.log(f"Transkrypcja Whisper ({model_size})...")
                yield log_capture.get_logs(), "", ""

                segments, info = processor.transcribe_video(file_path, lang_code, model_size)

                output_fmt = OUTPUT_FORMAT_MAP.get(output_format, "json")
                txt_file, _ = processor.save_transcription(
                    segments, info, file_path, output_fmt, lang_code
                )

                all_transcripts.append(txt_file)
                log_capture.log(f"Transkrypcja: {os.path.basename(txt_file)}")

                clear_gpu_memory()

            # Ekstrakcja
            if do_extraction and txt_file:
                log_capture.log("Ekstrakcja wiedzy...")
                kb_path = run_knowledge_extraction(txt_file, progress_adapter, log_capture)
                if kb_path:
                    all_kb_paths.append(kb_path)

            yield log_capture.get_logs(), txt_file or "", kb_path if 'kb_path' in dir() else ""

        # Podsumowanie wyników
        log_capture.log(f"Zakonczone! Przetworzone pliki: {len(files)}")
        final_transcript = all_transcripts[-1] if all_transcripts else ""
        final_kb = all_kb_paths[-1] if all_kb_paths else ""

        yield log_capture.get_logs(), final_transcript, final_kb

    except Exception as e:
        log_capture.error(str(e))
        yield log_capture.get_logs() + f"\n\n{format_error('transcription_failed', str(e))}", "", ""


def run_knowledge_extraction(
    txt_file: str,
    progress_adapter: GradioProgressAdapter,
    log_capture: LogCapture
) -> Optional[str]:
    """
    Wykonuje ekstrakcję wiedzy z pliku tekstowego.

    Returns:
        Ścieżka do pliku KB lub None
    """
    from src.utils.config import DATA_PROCESSED, CHUNK_SIZE, OVERLAP, MODEL_EXTRACTOR
    from src.core.text_cleaner import clean_transcript
    from src.utils.text_processing import smart_split_text
    from src.agents.extractor import KnowledgeExtractor
    from src.core.llm_engine import unload_model

    if not txt_file or not os.path.exists(txt_file):
        return None

    try:
        # Wczytaj i podziel tekst
        with open(txt_file, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        clean_text = clean_transcript(raw_text)
        chunks = smart_split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)

        if not chunks:
            log_capture.warning("Brak fragmentow do analizy")
            return None

        log_capture.log(f"Analizowanie {len(chunks)} fragmentow...")

        # Ekstrakcja
        knowledge_base = []
        extractor = KnowledgeExtractor()

        for i, chunk in enumerate(chunks):
            progress_pct = 50 + (40 * (i + 1) / len(chunks))
            progress_adapter.update(progress_pct, "extracting")

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
        log_capture.error(f"Blad ekstrakcji: {e}")
        return None


# =============================================================================
# TAB 2: NOTE GENERATION HANDLERS
# =============================================================================

def get_kb_files() -> List[str]:
    """
    Pobiera listę plików bazy wiedzy.

    Returns:
        Lista ścieżek do plików KB (posortowana wg czasu modyfikacji)
    """
    from src.utils.config import DATA_PROCESSED

    if not os.path.exists(DATA_PROCESSED):
        return []

    kb_files = []
    for f in os.listdir(DATA_PROCESSED):
        if f.endswith('_kb.json'):
            full_path = os.path.join(DATA_PROCESSED, f)
            kb_files.append(full_path)

    # Sortuj wg czasu modyfikacji (najnowsze pierwsze)
    kb_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    return kb_files


def load_kb_file(filepath: str) -> Tuple[int, int, int, int, str, str]:
    """
    Wczytuje plik KB i zwraca metryki.

    Returns:
        tuple: (segments, concepts, tools, tips, topics_str, preview_json)
    """
    if not filepath or not os.path.exists(filepath):
        return 0, 0, 0, 0, "", "{}"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            return 0, 0, 0, 0, "", "{}"

        segments = len(data)
        concepts = sum(len(item.get('key_concepts', [])) for item in data)
        tools = sum(len(item.get('tools', [])) for item in data)
        tips = sum(len(item.get('tips', [])) for item in data)

        # Zbierz unikalne tematy
        all_topics = []
        for item in data:
            all_topics.extend(item.get('topics', []))
        unique_topics = list(set(all_topics))[:10]
        topics_str = ", ".join(unique_topics)

        # Preview JSON (pierwsze 2 elementy)
        preview = json.dumps(data[:2], ensure_ascii=False, indent=2)

        return segments, concepts, tools, tips, topics_str, preview

    except Exception as e:
        return 0, 0, 0, 0, f"Blad: {e}", "{}"


def extract_topic_from_filename(filepath: str) -> str:
    """Wyciąga temat z nazwy pliku."""
    if not filepath:
        return ""

    topic = os.path.basename(filepath)

    # Usuń rozszerzenia i sufiksy
    for suffix in ['.json', '.txt', '_kb', '_transkrypcja', '_transcript']:
        topic = topic.replace(suffix, '')

    # Zamień separatory na spacje
    topic = topic.replace('_', ' ').replace('-', ' ')

    # Usuń datę z początku (YYYY-MM-DD lub YYYYMMDD)
    topic = re.sub(r'^\d{4}[-_]?\d{2}[-_]?\d{2}\s*', '', topic)

    return topic.strip().title()[:100]


def generate_note_streaming(
    kb_file_path: str,
    style: str,
    topic_name: str,
    custom_system_prompt: str = "",
    custom_user_prompt: str = "",
    source_url: str = "",
    source_title: str = "",
    duration: str = "",
    aliases: str = ""
) -> Generator[str, None, None]:
    """
    Generator streamujący treść notatki token po tokenie.

    Jest to główna implementacja streaming dla Tab 2.
    Używa wzorca generatora Gradio.

    Yields:
        Skumulowana treść (nie pojedyncze tokeny)
    """
    from src.agents.writer import ReportWriter
    from src.core.llm_engine import unload_model
    from src.utils.config import MODEL_WRITER

    if not kb_file_path or not os.path.exists(kb_file_path):
        yield format_error("no_kb_file")
        return

    # Auto-generuj temat z nazwy pliku
    if not topic_name.strip():
        topic_name = extract_topic_from_filename(kb_file_path)

    # Mapuj styl UI na backend
    backend_style = STYLE_MAP.get(style, "note")

    try:
        # Wczytaj bazę wiedzy
        with open(kb_file_path, 'r', encoding='utf-8') as f:
            knowledge_data = json.load(f)

        writer = ReportWriter()

        # Przygotuj metadata
        metadata = {
            'source_url': source_url.strip() if source_url else '',
            'source_title': source_title.strip() if source_title else '',
            'duration': duration.strip() if duration else '',
            'aliases': [a.strip() for a in aliases.split(',') if a.strip()] if aliases else []
        }

        # Przygotuj kontekst
        context_str = writer._prepare_context(knowledge_data)

        # Buduj prompty
        if custom_system_prompt and custom_system_prompt.strip():
            system_prompt = custom_system_prompt.strip()
        else:
            system_prompt = "Jestes ekspertem technicznym piszacym notatki w jezyku polskim."

        if custom_user_prompt and custom_user_prompt.strip():
            final_user_prompt = custom_user_prompt.strip()
            final_user_prompt = final_user_prompt.replace("{topic_name}", topic_name)
            final_user_prompt = final_user_prompt.replace("{context_items}", context_str)
        else:
            final_user_prompt = writer.prompt_manager.build_writer_prompt(
                context_str, topic_name, content_type=backend_style
            )

        # Buduj frontmatter
        yaml_header = writer._build_frontmatter(topic_name, [], backend_style, metadata)

        # Yield header najpierw
        yield yaml_header

        # Stream content
        accumulated = yaml_header
        for token in writer.llm.generate_stream(system_prompt, final_user_prompt):
            accumulated += token
            yield accumulated

        # Dodaj source index na końcu
        source_index = writer._build_source_index(knowledge_data)
        final_content = accumulated + source_index
        yield final_content

    except Exception as e:
        yield f"{format_error('generation_failed', str(e))}"
    finally:
        try:
            unload_model(MODEL_WRITER)
        except Exception:
            pass


def update_style_description(style: str) -> Tuple[str, str, str]:
    """
    Aktualizuje opis stylu i domyślne prompty.

    Returns:
        tuple: (description, system_prompt, user_prompt)
    """
    from src.gui.constants import STYLE_DESCRIPTIONS
    from src.utils.prompts_config import PROMPT_TEMPLATES

    desc = STYLE_DESCRIPTIONS.get(style, "")
    backend_key = STYLE_MAP.get(style, "standard")

    template = PROMPT_TEMPLATES.get(backend_key, PROMPT_TEMPLATES.get("standard", {}))
    system_prompt = template.get("system", "")
    user_prompt = template.get("user", "")

    return f"*{desc}*", system_prompt, user_prompt


def save_to_obsidian(content: str, filename: str, vault_path: str) -> str:
    """
    Zapisuje notatkę do Obsidian vault.

    Returns:
        Komunikat statusu
    """
    if not content or not content.strip():
        return format_error("no_content")

    if not filename or not filename.strip():
        return format_error("no_filename")

    if not vault_path or not os.path.isdir(vault_path):
        return format_error("invalid_obsidian_path")

    try:
        # Sanitize filename
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename.strip())
        if not safe_filename.endswith('.md'):
            safe_filename += '.md'

        filepath = os.path.join(vault_path, safe_filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return format_success("obsidian_save_complete", filename=safe_filename)

    except Exception as e:
        return format_error("save_failed", str(e))


def save_note_locally(content: str, filename: str) -> str:
    """
    Zapisuje notatkę lokalnie w DATA_OUTPUT.

    Returns:
        Komunikat statusu
    """
    from src.utils.config import DATA_OUTPUT

    if not content or not content.strip():
        return format_error("no_content")

    if not filename or not filename.strip():
        return format_error("no_filename")

    try:
        os.makedirs(DATA_OUTPUT, exist_ok=True)

        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename.strip())
        if not safe_filename.endswith('.md'):
            safe_filename += '.md'

        filepath = os.path.join(DATA_OUTPUT, safe_filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return format_success("save_complete", filepath=filepath)

    except Exception as e:
        return format_error("save_failed", str(e))


def generate_filename_from_kb(kb_path: str, style: str) -> str:
    """Generuje nazwę pliku na podstawie KB i stylu."""
    if not kb_path:
        return ""

    topic = extract_topic_from_filename(kb_path)
    date_str = datetime.now().strftime("%Y-%m-%d")
    style_suffix = STYLE_MAP.get(style, "note")

    return f"{topic}_{style_suffix}_{date_str}.md"


def generate_tags_for_content(content: str, auto_tag_enabled: bool) -> str:
    """
    Generuje tagi dla wygenerowanej treści używając TaggerAgent.

    Args:
        content: Wygenerowana treść notatki
        auto_tag_enabled: Czy auto-tagowanie jest włączone

    Returns:
        String z tagami oddzielonymi przecinkami lub komunikat
    """
    if not auto_tag_enabled:
        return "Tagowanie wylaczone"

    if not content or not content.strip():
        return "Brak tresci do analizy"

    try:
        from src.agents.tagger import TaggerAgent
        from src.core.llm_engine import unload_model
        from src.utils.config import MODEL_TAGGER

        # Wyciągnij treść bez frontmatter YAML
        clean_content = content
        if content.startswith("---"):
            # Znajdź koniec frontmatter
            second_dash = content.find("---", 3)
            if second_dash != -1:
                clean_content = content[second_dash + 3:].strip()

        # Ogranicz długość tekstu do analizy (max 4000 znaków)
        text_for_tagging = clean_content[:4000]

        # Wywołaj TaggerAgent
        tagger = TaggerAgent()
        tags = tagger.generate_tags(text_for_tagging)

        # Wyładuj model po użyciu
        try:
            unload_model(MODEL_TAGGER)
        except Exception:
            pass

        if tags:
            return ", ".join(tags)
        return "Nie wygenerowano tagow"

    except Exception as e:
        return f"Blad tagowania: {str(e)[:100]}"


def inject_tags_into_frontmatter(content: str, tags_str: str) -> str:
    """
    Wstrzykuje tagi do istniejącego frontmatter YAML.

    Args:
        content: Treść z frontmatter
        tags_str: Tagi oddzielone przecinkami

    Returns:
        Treść z zaktualizowanym frontmatter
    """
    if not content or not tags_str:
        return content

    # Parsuj tagi
    if tags_str.startswith("Blad") or tags_str.startswith("Tagowanie") or tags_str.startswith("Brak"):
        return content

    tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
    if not tags_list:
        return content

    # Znajdź i zamień linię tags: [] na tags: [tag1, tag2, ...]
    if content.startswith("---"):
        # Format tagów dla YAML
        tags_yaml = str(tags_list)  # Python list to YAML-like string

        # Zamień tags: [] na tags: [...]
        content = re.sub(
            r'tags:\s*\[\]',
            f'tags: {tags_yaml}',
            content,
            count=1
        )

    return content


# =============================================================================
# TAB 3: BATCH PROCESSING HANDLERS
# =============================================================================

def count_urls(text: str) -> str:
    """Liczy URL-e w tekście."""
    if not text or not text.strip():
        return "0 URLi"

    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    urls = [l for l in lines if l.startswith(('http://', 'https://'))]

    return f"{len(urls)} URLi"


def run_batch_wizard(
    urls_text: str,
    model_size: str,
    progress: gr.Progress = gr.Progress()
) -> Generator[Tuple[str, str], None, None]:
    """
    Przetwarza wiele URLi wsadowo.

    Yields:
        tuple: (log_output, results_summary)
    """
    from src.utils.config import DATA_OUTPUT, WHISPER_LANGUAGES

    reset_cancel()
    stop_event = get_stop_event()

    if not urls_text or not urls_text.strip():
        yield "Brak URLi do przetworzenia", ""
        return

    # Parsuj URLe
    lines = [l.strip() for l in urls_text.strip().split('\n') if l.strip()]
    urls = [l for l in lines if l.startswith(('http://', 'https://'))]

    if not urls:
        yield "Nie znaleziono prawidlowych URLi", ""
        return

    log_capture = LogCapture()
    progress_adapter = GradioProgressAdapter(progress)

    results = []
    failed = []

    try:
        from src.core.processor import Processor
        from src.core.gpu_manager import clear_gpu_memory

        processor = Processor(
            logger=log_capture,
            stop_event=stop_event,
            progress_callback=progress_adapter.update
        )

        for i, url in enumerate(urls):
            if stop_event.is_set():
                log_capture.log("Przetwarzanie anulowane!")
                break

            log_capture.log(f"\n--- [{i+1}/{len(urls)}] {url[:50]}... ---")
            yield log_capture.get_logs(), ""

            try:
                # Pobierz
                downloaded = processor.download_video(url, DATA_OUTPUT, "bestaudio", "192")
                if not downloaded:
                    failed.append(url)
                    log_capture.error(f"Nie udalo sie pobrac: {url}")
                    continue

                audio_file = downloaded[0].get('video') or downloaded[0].get('audio')

                # Transkrybuj
                segments, info = processor.transcribe_video(audio_file, "pl", model_size)
                txt_file, _ = processor.save_transcription(segments, info, audio_file, "txt", "pl")

                results.append({
                    'url': url,
                    'transcript': txt_file,
                    'status': 'success'
                })

                log_capture.log(f"OK: {os.path.basename(txt_file)}")
                clear_gpu_memory()

            except Exception as e:
                failed.append(url)
                log_capture.error(f"Blad: {str(e)[:100]}")

            # Aktualizuj progress
            progress_adapter.update((i + 1) / len(urls) * 100, "batch")
            yield log_capture.get_logs(), ""

        # Podsumowanie
        summary = f"\n\n=== PODSUMOWANIE ===\n"
        summary += f"Przetworzone: {len(results)}/{len(urls)}\n"
        summary += f"Bledy: {len(failed)}\n"

        if results:
            summary += "\nPliki:\n"
            for r in results:
                summary += f"- {os.path.basename(r['transcript'])}\n"

        log_capture.log(summary)
        yield log_capture.get_logs(), json.dumps(results, indent=2, ensure_ascii=False)

    except Exception as e:
        log_capture.error(f"Blad krytyczny: {str(e)}")
        yield log_capture.get_logs(), ""


# =============================================================================
# TAB NAVIGATION HELPERS
# =============================================================================

def go_to_notes_tab(kb_path: str) -> Tuple:
    """
    Przechodzi do Tab 2 z wybranym plikiem KB.

    Returns:
        Tuple wartości dla outputs
    """
    files = get_kb_files()

    # Wybierz plik
    selected = kb_path if kb_path and kb_path in files else (files[0] if files else None)

    if selected:
        metrics = load_kb_file(selected)
        topic = extract_topic_from_filename(selected)

        return (
            gr.update(choices=files, value=selected),  # kb_file_dropdown
            gr.Tabs(selected="tab_notes"),              # tabs
            topic,                                      # topic_input
            *metrics                                    # metryki
        )

    return (
        gr.update(choices=files),
        gr.Tabs(selected="tab_notes"),
        "",
        0, 0, 0, 0, "", "{}"
    )


def show_create_note_button(kb_path: str) -> dict:
    """Pokazuje przycisk 'Stwórz notatkę' jeśli mamy KB."""
    visible = bool(kb_path and os.path.exists(kb_path))
    return gr.update(visible=visible)
