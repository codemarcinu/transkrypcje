import os
from src.core.downloader import Downloader
from src.core.transcriber import Transcriber
from src.core.summarizer import Summarizer
from src.core.osint_analyzer import OsintAnalyzer
from src.core.gpu_manager import clear_gpu_memory
from src.utils.helpers import validate_url, validate_path, check_disk_space, check_ffmpeg
from src.utils.config import DEFAULT_OLLAMA_MODEL
from src.utils.subtitle_converter import convert_subtitle_to_txt

class ContentProcessor:
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

    def run_content_generation(self, input_file, topic, model_name="bielik"):
        """Uruchamia pełny proces Map-Reduce z czyszczeniem VRAM."""
        from main_pipeline import run_pipeline
        from src.utils.config import DATA_OUTPUT, MODEL_EXTRACTOR, MODEL_WRITER
        from src.core.llm_engine import unload_model
        
        self.logger.log(f"Inicjowanie generowania treści dla {input_file}...")
        
        # Prewencyjne czyszczenie VRAM (wyładowanie Whisper i starych modeli)
        try:
            clear_gpu_memory()
            # Próbujemy zwolnić oba modele LLM na wszelki wypadek
            unload_model(MODEL_EXTRACTOR)
            unload_model(MODEL_WRITER)
        except Exception as e:
            self.logger.log(f"Wskazówka: Nie udało się prewencyjnie zwolnić VRAM: {e}")

        try:
            run_pipeline(input_path=input_file, output_dir=DATA_OUTPUT, topic=topic)
            self.logger.log("Pipeline zakończony.")
            
            # Predict output path as main_pipeline does:
            # os.path.join(output_dir, f"Podrecznik_{filename.replace('.txt', '.md')}")
            filename = os.path.basename(input_file)
            result_path = os.path.join(DATA_OUTPUT, f"Podrecznik_{filename.replace('.txt', '.md')}")
            return result_path
        except Exception as e:
            self.logger.log(f"Błąd pipeline'u: {e}")
            raise e
