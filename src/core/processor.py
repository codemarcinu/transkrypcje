from src.core.downloader import Downloader
from src.core.transcriber import Transcriber
from src.core.summarizer import Summarizer
from src.core.osint_analyzer import OsintAnalyzer
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
        return self.transcriber.save_transcription(segments, info, filename, output_format, language)

    def summarize_text(self, text, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
        return self.summarizer.summarize_text(text, model_name, max_chars, style)

    def summarize_from_file(self, file_path, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
        return self.summarizer.summarize_from_file(file_path, model_name, max_chars, style)

    def run_content_generation(self, input_file, output_file, topic="Narzędzia OSINT, Krypto i Techniki Śledcze"):
        # Używamy nowego pipeline'u (Instructor + Qwen/Bielik)
        from main_pipeline import run_pipeline
        # output_file is full path, but run_pipeline expects dir. 
        # However, run_pipeline generates its own filename "Podrecznik_...".
        # We should probably respect output_file path or just pass the dir.
        # For compatibility with GUI which expects specific file but run_pipeline decides name...
        # Let's pass the directory of output_file
        output_dir = os.path.dirname(output_file)
        
        # Przekierowanie stdout/stderr do loggera GUI to wyższa szkoła jazdy, 
        # ale run_pipeline drukuje na konsolę. 
        # W GUI zobaczymy to w terminalu, a w logach GUI tylko "Rozpoczynam...".
        self.logger.log(f"Uruchamianie generatora treści dla {input_file} (Temat: {topic})...")
        try:
            run_pipeline(input_file, output_dir, topic=topic)
            self.logger.log("Pipeline zakończony.")
        except Exception as e:
            self.logger.log(f"Błąd pipeline'u: {e}")
            raise e
