from src.core.downloader import Downloader
from src.core.transcriber import Transcriber
from src.core.summarizer import Summarizer
from src.utils.helpers import validate_url, validate_path, check_disk_space, check_ffmpeg

class Processor:
    def __init__(self, logger, stop_event, progress_callback):
        self.logger = logger
        self.stop_event = stop_event
        self.progress_callback = progress_callback
        
        self.downloader = Downloader(logger, stop_event, progress_callback)
        self.transcriber = Transcriber(logger, stop_event, progress_callback)
        self.summarizer = Summarizer(logger, stop_event, progress_callback)

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
        """Pobiera wideo (lub listę wideo) z YouTube. Zwraca listę ścieżek do plików."""
        return self.downloader.download_video(url, save_path, quality, audio_quality)

    def convert_to_mp3(self, input_path, output_path=None):
        return self.downloader.convert_to_mp3(input_path, output_path)

    def transcribe_video(self, filename, language, model_size):
        return self.transcriber.transcribe_video(filename, language, model_size)

    def save_transcription(self, segments, info, filename, output_format, language):
        return self.transcriber.save_transcription(segments, info, filename, output_format, language)

    def summarize_text(self, text, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
        return self.summarizer.summarize_text(text, model_name, max_chars, style)
