import os
from src.core.downloader import Downloader
from src.core.transcriber import Transcriber
from src.core.summarizer import Summarizer
from src.core.osint_analyzer import OsintAnalyzer
from src.core.gpu_manager import clear_gpu_memory
from src.agents.extractor import KnowledgeExtractor
from src.agents.writer import ReportWriter
from src.agents.tagger import TaggerAgent
from src.core.llm_engine import unload_model
from src.utils.helpers import validate_url, validate_path, check_disk_space, check_ffmpeg
from src.utils.config import DEFAULT_OLLAMA_MODEL
from src.utils.subtitle_converter import convert_subtitle_to_txt

class Processor:
    def __init__(self, logger, stop_event, progress_callback):
        self.logger = logger
        self.stop_event = stop_event
        self.progress_callback = progress_callback
        
        self.downloader = Downloader(logger, stop_event, progress_callback)
        self.transcriber = Transcriber(logger, stop_event, progress_callback)
        self.summarizer = Summarizer(logger, stop_event, progress_callback)
        self.osint_analyzer = OsintAnalyzer(logger, stop_event, progress_callback)

    # Proxy methods for convenience or direct access
    def validate_url(self, url):
        return validate_url(url)

    def validate_path(self, path):
        return validate_path(path)
    
    def check_disk_space(self, path, min_gb=1):
        return check_disk_space(path, min_gb)

    def check_ffmpeg(self):
        return check_ffmpeg()

    def check_ollama_status(self):
        return self.summarizer.check_ollama_status()
    
    def download_video(self, url, save_path, quality, audio_quality="192"):
        """Pobiera wideo z YouTube. Zwraca listę słowników {'video': path, 'subtitles': path_or_None}."""
        return self.downloader.download_video(url, save_path, quality, audio_quality)

    def convert_subtitles_to_txt(self, subtitle_path, output_path=None):
        return convert_subtitle_to_txt(subtitle_path, output_path)

    def convert_to_mp3(self, input_path, output_path=None):
        return self.downloader.convert_to_mp3(input_path, output_path)

    def transcribe_video(self, filename, language, model_size):
        return self.transcriber.transcribe_video(filename, language, model_size)

    def save_transcription(self, segments, info, filename, output_format, language):
        """Zapisuje transkrypcję. Zwraca (output_file, json_file)."""
        return self.transcriber.save_transcription(segments, info, filename, output_format, language)

    def convert_json_transcription(self, json_path, output_format):
        """Konwertuje istniejący JSON transkrypcji do innego formatu."""
        from src.core.transcriber import Transcriber

        if output_format == "txt":
            return Transcriber.convert_json_to_txt(json_path)
        elif output_format == "txt_no_timestamps":
            return Transcriber.convert_json_to_txt(json_path, with_timestamps=False)
        elif output_format == "srt":
            return Transcriber.convert_json_to_srt(json_path)
        elif output_format == "vtt":
            return Transcriber.convert_json_to_vtt(json_path)
        else:
            return json_path

    def summarize_text(self, text, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
        return self.summarizer.summarize_text(text, model_name, max_chars, style)

    def summarize_from_file(self, file_path, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
        return self.summarizer.summarize_from_file(file_path, model_name, max_chars, style)

    def process_workflow(self, source, prompt_style="note", enable_tagging=True):
        """
        Główny workflow: Pobieranie -> Transkrypcja -> Ekstrakcja -> Pisanie -> Tagowanie.
        Zintegrowana wersja z main_pipeline, ale przystosowana do GUI.
        """
        from src.utils.config import DATA_OUTPUT, MODEL_EXTRACTOR, MODEL_WRITER, MODEL_TAGGER
        import json
        from src.core.text_cleaner import clean_transcript
        from src.utils.text_processing import smart_split_text
        from src.utils.config import CHUNK_SIZE, OVERLAP
        from tqdm import tqdm

        # 1. Przygotowanie źródła
        input_path = source
        if source.startswith(("http://", "https://")):
            self.logger.log(f"[PROCESSOR] Pobieranie z URL: {source}")
            download_results = self.download_video(source, DATA_OUTPUT, "bestaudio")
            if not download_results:
                raise Exception("Nie udało się pobrać materiału.")
            # Szukamy audio lub wideo
            input_path = download_results[0].get('video') or download_results[0].get('audio')

        # 2. Transkrypcja (jeśli potrzebna)
        if not input_path.endswith('.txt'):
            self.logger.log(f"[PROCESSOR] Transkrypcja Whisper...")
            segments, info = self.transcribe_video(input_path, language=None, model_size="large-v3")
            txt_path, _ = self.save_transcription(segments, info, input_path, output_format="txt", language=None)
            input_path = txt_path
            clear_gpu_memory()

        # 3. Wczytywanie i czyszczenie
        with open(input_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
        clean_text = clean_transcript(raw_text)
        chunks = smart_split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)

        # 4. Ekstrakcja
        knowledge_base = []
        self.logger.log(f"[PROCESSOR] Ekstrakcja wiedzy ({len(chunks)} fragmentów)...")
        try:
            extractor = KnowledgeExtractor()
            for i, chunk in enumerate(chunks):
                graph = extractor.extract_knowledge(chunk, chunk_id=i)
                knowledge_base.append(graph.model_dump())
        finally:
            unload_model(MODEL_EXTRACTOR)

        # 5. Pisanie (Bielik)
        self.logger.log(f"[PROCESSOR] Generowanie treści (Styl: {prompt_style})...")
        content = ""
        try:
            writer = ReportWriter()
            # prompt_style mapowany w GUI na np. 'deep_dive', 'note'
            content = writer.generate_chapter(
                topic_name=os.path.basename(input_path),
                aggregated_data=knowledge_base,
                mode=prompt_style
            )
        finally:
            unload_model(MODEL_WRITER)

        # 6. Tagowanie (Qwen)
        tags = []
        if enable_tagging:
            self.logger.log("[PROCESSOR] Generowanie tagów...")
            try:
                tagger = TaggerAgent()
                tags = tagger.generate_tags(content)
            finally:
                unload_model(MODEL_TAGGER)

        # 7. Zapis końcowy
        output_filename = f"Analiza_{os.path.basename(input_path)}.md"
        output_path = os.path.join(DATA_OUTPUT, output_filename)
        
        # Ostateczne złożenie z tagami (jeśli writer ich nie dodał w YAML)
        if "tags: []" in content and tags:
            content = content.replace("tags: []", f"tags: {tags}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return {
            "content": content,
            "tags": tags,
            "file_path": output_path
        }

# Alias dla kompatybilności wstecznej
ContentProcessor = Processor
