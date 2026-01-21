import os
import json
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
        """Zapisuje transkrypcję - ZAWSZE najpierw do JSON, potem konwertuje do wybranego formatu.

        Returns:
            tuple: (output_file, json_file) - ścieżki do pliku wyjściowego i bazowego JSON
        """
        base_name = os.path.splitext(filename)[0]
        json_file = base_name + "_transkrypcja.json"

        # 1. ZAWSZE zapisz do JSON (konsumuje generator, zwraca listę segmentów)
        segments_list = self._save_json(segments, info, json_file, language)

        # 2. Konwertuj do wybranego formatu (używa listy, nie generatora)
        if output_format == "json":
            output_file = json_file
        elif output_format == "txt":
            output_file = base_name + "_transkrypcja.txt"
            self._convert_to_txt(segments_list, info, output_file, language)
        elif output_format == "srt":
            output_file = base_name + "_transkrypcja.srt"
            self._convert_to_srt(segments_list, output_file)
        elif output_format == "vtt":
            output_file = base_name + "_transkrypcja.vtt"
            self._convert_to_vtt(segments_list, output_file)
        elif output_format == "txt_no_timestamps":
            output_file = base_name + "_transkrypcja.txt"
            self._convert_to_txt_no_timestamps(segments_list, info, output_file, language)
        else:
            output_file = base_name + "_transkrypcja.txt"
            self._convert_to_txt(segments_list, info, output_file, language)

        # Cleanup memory after consumption
        self.current_model = None
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return output_file, json_file

    def _save_json(self, segments, info, filename, language):
        """Konsumuje generator Whispera i zapisuje do JSON. Zwraca listę segmentów."""
        segments_list = []

        detected_lang = getattr(info, 'language', language or 'nieznany')
        lang_prob = getattr(info, 'language_probability', 0.0)
        duration = getattr(info, 'duration', 0.0)

        with open(filename, "w", encoding="utf-8") as f:
            # Zapisujemy nagłówek JSON i otwieramy tablicę segmentów
            header = {
                "language": detected_lang,
                "language_probability": lang_prob,
                "duration": duration,
                "segments": []
            }

            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")

                seg_data = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                }
                segments_list.append(seg_data)
                header["segments"].append(seg_data)

                if duration > 0:
                    percent = (segment.end / duration) * 100
                    self.progress_callback(percent, "transcribing")

            json.dump(header, f, ensure_ascii=False, indent=2)

        self.logger.log(f"Zapisano bazowy JSON: {filename}")
        return segments_list

    def _convert_to_txt(self, segments_list, info, filename, language):
        """Konwertuje listę segmentów do formatu TXT z timestamps."""
        detected_lang = getattr(info, 'language', language or 'nieznany')
        lang_prob = getattr(info, 'language_probability', 0.0)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Język wykryty: {detected_lang} (pewność: {lang_prob:.2%})\n")
            f.write("-" * 40 + "\n\n")

            for seg in segments_list:
                line = f"[{format_time(seg['start'])} -> {format_time(seg['end'])}] {seg['text']}\n"
                f.write(line)

    def _convert_to_txt_no_timestamps(self, segments_list, info, filename, language):
        """Konwertuje listę segmentów do formatu TXT bez timestamps."""
        detected_lang = getattr(info, 'language', language or 'nieznany')
        lang_prob = getattr(info, 'language_probability', 0.0)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Język wykryty: {detected_lang} (pewność: {lang_prob:.2%})\n")
            f.write("-" * 40 + "\n\n")

            for seg in segments_list:
                f.write(seg['text'] + " ")

    def _convert_to_srt(self, segments_list, filename):
        """Konwertuje listę segmentów do formatu SRT."""
        with open(filename, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments_list, 1):
                start = format_srt_time(seg['start'])
                end = format_srt_time(seg['end'])
                f.write(f"{i}\n{start} --> {end}\n{seg['text']}\n\n")

    def _convert_to_vtt(self, segments_list, filename):
        """Konwertuje listę segmentów do formatu VTT."""
        with open(filename, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for seg in segments_list:
                start = format_vtt_time(seg['start'])
                end = format_vtt_time(seg['end'])
                f.write(f"{start} --> {end}\n{seg['text']}\n\n")

    # === STATYCZNE METODY KONWERSJI Z PLIKU JSON ===

    @staticmethod
    def convert_json_to_txt(json_path, output_path=None, with_timestamps=True):
        """Konwertuje plik JSON do TXT."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if output_path is None:
            output_path = json_path.replace('.json', '.txt')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"Język wykryty: {data['language']} (pewność: {data['language_probability']:.2%})\n")
            f.write("-" * 40 + "\n\n")

            for seg in data['segments']:
                if with_timestamps:
                    f.write(f"[{format_time(seg['start'])} -> {format_time(seg['end'])}] {seg['text']}\n")
                else:
                    f.write(seg['text'] + " ")

        return output_path

    @staticmethod
    def convert_json_to_srt(json_path, output_path=None):
        """Konwertuje plik JSON do SRT."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if output_path is None:
            output_path = json_path.replace('.json', '.srt')

        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(data['segments'], 1):
                start = format_srt_time(seg['start'])
                end = format_srt_time(seg['end'])
                f.write(f"{i}\n{start} --> {end}\n{seg['text']}\n\n")

        return output_path

    @staticmethod
    def convert_json_to_vtt(json_path, output_path=None):
        """Konwertuje plik JSON do VTT."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if output_path is None:
            output_path = json_path.replace('.json', '.vtt')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            for seg in data['segments']:
                start = format_vtt_time(seg['start'])
                end = format_vtt_time(seg['end'])
                f.write(f"{start} --> {end}\n{seg['text']}\n\n")

        return output_path

