import os
import torch
from faster_whisper import WhisperModel
from src.utils.config import DEVICE, COMPUTE_TYPE
from src.utils.helpers import format_time, format_srt_time, format_vtt_time

class Transcriber:
    def __init__(self, logger, stop_event, progress_callback):
        self.logger = logger
        self.stop_event = stop_event
        self.progress_callback = progress_callback
        self.current_model = None

    def transcribe_video(self, filename, language, model_size):
        """Transkrybuje plik używając Whisper (Generator)"""
        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")
        
        self.logger.log("Ładowanie modelu Whisper...")

        if DEVICE == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            self.logger.log(f"Używam GPU: {gpu_name}")
        else:
            self.logger.log("UWAGA: GPU nie wykryte! Używam CPU (będzie wolniej).")

        self.progress_callback(0, f"Wczytywanie modelu {model_size} do pamięci ({DEVICE})...")

        try:
            models_dir = os.path.join(os.getcwd(), "models")
            if not os.path.exists(models_dir):
                os.makedirs(models_dir, exist_ok=True)
            self.logger.log(f"Katalog z modelami: {models_dir}")

            model = WhisperModel(model_size, device=DEVICE, compute_type=COMPUTE_TYPE, download_root=models_dir)
            self.current_model = model
        except Exception as e:
            raise Exception(f"Nie można załadować modelu Whisper: {str(e)}")

        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")

        self.logger.log(f"Rozpoczynam transkrypcję (język: {language or 'auto'})...")

        try:
            # Faster-Whisper transcribe returns (segments_generator, info)
            segments, info = model.transcribe(
                filename,
                language=language,
                beam_size=5,
                vad_filter=True,
            )
            # DO NOT list(segments) here - keep it as generator!
        except Exception as e:
            raise Exception(f"Błąd podczas transkrypcji: {str(e)}")

        return segments, info

    def save_transcription(self, segments, info, filename, output_format, language):
        """Zapisuje transkrypcję iterując po generatorze. Zwraca ścieżkę do pliku."""
        base_name = os.path.splitext(filename)[0]
        output_file = ""
        
        # Note: We can only consume the generator ONCE.
        
        if output_format == "txt":
            output_file = base_name + "_transkrypcja.txt"
            self._save_txt(segments, info, output_file, language)
        elif output_format == "srt":
            output_file = base_name + "_transkrypcja.srt"
            self._save_srt(segments, output_file)
        elif output_format == "vtt":
            output_file = base_name + "_transkrypcja.vtt"
            self._save_vtt(segments, output_file)
        elif output_format == "txt_no_timestamps":
            output_file = base_name + "_transkrypcja.txt"
            self._save_txt_no_timestamps(segments, info, output_file, language)
        else:
            output_file = base_name + "_transkrypcja.txt"
            self._save_txt(segments, info, output_file, language)

        # Cleanup memory after consumption
        self.current_model = None
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return output_file

    def _save_txt(self, segments, info, filename, language):
        with open(filename, "w", encoding="utf-8") as f:
            detected_lang = getattr(info, 'language', language or 'nieznany')
            lang_prob = getattr(info, 'language_probability', 0.0)
            f.write(f"Język wykryty: {detected_lang} (pewność: {lang_prob:.2%})\n")
            f.write("-" * 40 + "\n\n")

            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                line = f"[{format_time(segment.start)} -> {format_time(segment.end)}] {segment.text}\n"
                f.write(line)
                f.flush() # CRITICAL: Write immediately to disk
                
                if hasattr(info, 'duration') and info.duration > 0:
                    percent = (segment.end / info.duration) * 100
                    self.progress_callback(percent, "transcribing")

    def _save_txt_no_timestamps(self, segments, info, filename, language):
        with open(filename, "w", encoding="utf-8") as f:
            detected_lang = getattr(info, 'language', language or 'nieznany')
            lang_prob = getattr(info, 'language_probability', 0.0)
            f.write(f"Język wykryty: {detected_lang} (pewność: {lang_prob:.2%})\n")
            f.write("-" * 40 + "\n\n")

            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                f.write(segment.text + " ")
                f.flush()
                
                if hasattr(info, 'duration') and info.duration > 0:
                    percent = (segment.end / info.duration) * 100
                    self.progress_callback(percent, "transcribing")

    def _save_srt(self, segments, filename):
        with open(filename, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                start = format_srt_time(segment.start)
                end = format_srt_time(segment.end)
                f.write(f"{i}\n{start} --> {end}\n{segment.text}\n\n")
                f.flush()


    def _save_vtt(self, segments, filename):
        full_text = ""
        with open(filename, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                start = format_vtt_time(segment.start)
                end = format_vtt_time(segment.end)
                f.write(f"{start} --> {end}\n{segment.text}\n\n")
                f.flush()
                
                full_text += segment.text + " "

        return full_text.strip()
