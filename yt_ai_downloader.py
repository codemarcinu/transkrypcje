import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import yt_dlp
import os
import threading
from faster_whisper import WhisperModel
import time
import re
import requests
import shutil
import subprocess
import platform
from pathlib import Path
import logging
import traceback

import torch

# Dodaj ścieżkę do FFmpeg (WinGet) jeśli nie jest wykrywany
ffmpeg_path = os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links")
if os.path.exists(ffmpeg_path) and ffmpeg_path not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + ffmpeg_path


# Konfiguracja modelu AI - domyślne wartości
DEFAULT_MODEL_SIZE = "medium"
DEFAULT_LANGUAGE = "pl"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# Dostępne języki dla Whisper
WHISPER_LANGUAGES = {
    "Auto": None,
    "Polski": "pl",
    "Angielski": "en",
    "Niemiecki": "de",
    "Francuski": "fr",
    "Hiszpański": "es",
    "Włoski": "it",
    "Rosyjski": "ru",
    "Japoński": "ja",
    "Chiński": "zh",
}

# Dostępne rozmiary modeli Whisper
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]


class VideoProcessor:
    def __init__(self, log_callback, progress_callback, stop_event):
        self.log = log_callback
        self.progress = progress_callback
        self.stop_event = stop_event
        self.current_model = None

    def validate_url(self, url):
        """Walidacja URL YouTube"""
        if not url or not url.strip():
            return False
        youtube_regex = (
            r"(https?://)?(www\.)?"
            r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
            r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
        )
        return re.match(youtube_regex, url.strip())

    def validate_path(self, path):
        """Walidacja ścieżki zapisu"""
        if not path or not path.strip():
            return False, "Ścieżka nie może być pusta"
        
        path = path.strip()
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                return False, f"Nie można utworzyć katalogu: {e}"
        
        if not os.access(path, os.W_OK):
            return False, "Brak uprawnień do zapisu w tym katalogu"
        
        return True, "OK"

    def check_disk_space(self, path, min_gb=1):
        """Sprawdza dostępne miejsce na dysku"""
        try:
            stat = shutil.disk_usage(path)
            free_gb = stat.free / (1024**3)
            if free_gb < min_gb:
                return False, f"Za mało miejsca na dysku ({free_gb:.2f} GB dostępne, wymagane: {min_gb} GB)"
            return True, f"{free_gb:.2f} GB dostępne"
        except Exception as e:
            return True, "Nie można sprawdzić miejsca"  # Nie blokuj jeśli nie można sprawdzić

    def check_ffmpeg(self):
        """Sprawdza czy FFmpeg jest zainstalowany"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            return True, "FFmpeg dostępny"
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False, "FFmpeg nie jest zainstalowany lub nie jest w PATH"

    def sanitize_filename(self, filename):
        """Sanityzuje nazwę pliku"""
        # Usuń niebezpieczne znaki
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Ogranicz długość
        if len(filename) > 200:
            filename = filename[:200]
        return filename

    def get_file_size(self, filepath):
        """Zwraca rozmiar pliku w czytelnej formie"""
        try:
            size = os.path.getsize(filepath)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.2f} {unit}"
                size /= 1024.0
            return f"{size:.2f} TB"
        except:
            return "Nieznany"

    def check_file_exists(self, filepath):
        """Sprawdza czy plik istnieje i zwraca unikalną nazwę jeśli potrzeba"""
        if not os.path.exists(filepath):
            return filepath, False
        
        base, ext = os.path.splitext(filepath)
        counter = 1
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        return f"{base}_{counter}{ext}", True

    def download_video(self, url, save_path, quality, audio_quality="192"):
        """Pobiera wideo z YouTube"""
        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")
        
        self.log(f"Pobieranie wideo ({quality})...")
        self.progress(0, "downloading")

        # Opcje wspólne
        common_opts = {
            "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"),
            "progress_hooks": [self.yt_dlp_hook],
            "writethumbnail": False,
            "writeinfojson": False,
            "keepvideo": False,
            "noplaylist": True,  # Nie pobieraj playlist
            "socket_timeout": 30,  # Timeout 30 sekund
        }

        if quality == "best":
            ydl_opts = {
                **common_opts,
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "postprocessors": [
                    {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
                ],
            }
        elif quality == "worst":
            ydl_opts = {
                **common_opts,
                "format": "worst",
                "merge_output_format": "mp4",
                "postprocessors": [
                    {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
                ],
            }
        elif quality == "audio_only":
            ydl_opts = {
                **common_opts,
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": audio_quality,
                    }
                ],
            }

        filename = ""
        file_size = 0
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                # Korekta nazwy pliku po konwersji
                base = os.path.splitext(filename)[0]
                if quality == "audio_only":
                    filename = base + ".mp3"
                else:
                    filename = base + ".mp4"
                
                # Sprawdź rozmiar pliku
                if os.path.exists(filename):
                    file_size = os.path.getsize(filename)
                    size_str = self.get_file_size(filename)
                    self.log(f"Rozmiar pliku: {size_str}")

        except yt_dlp.utils.DownloadError as e:
            raise Exception(f"Błąd pobierania: {str(e)}")
        except Exception as e:
            raise Exception(f"Nieoczekiwany błąd podczas pobierania: {str(e)}")

        if self.stop_event.is_set():
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                except:
                    pass
            raise InterruptedError("Operacja anulowana przez użytkownika")

        self.progress(100, "downloading")
        return filename

    def yt_dlp_hook(self, d):
        """Hook dla postępu pobierania"""
        if self.stop_event.is_set():
            raise InterruptedError("Anulowano")
        
        if d["status"] == "downloading":
            try:
                p = d.get("_percent_str", "0%").replace("%", "")
                percent = float(p)
                self.progress(percent, "downloading")
                
                # Pokaż prędkość pobierania jeśli dostępna
                if "speed" in d and d["speed"]:
                    speed = d["speed"]
                    if speed > 1024 * 1024:
                        speed_str = f"{speed / (1024*1024):.2f} MB/s"
                    elif speed > 1024:
                        speed_str = f"{speed / 1024:.2f} KB/s"
                    else:
                        speed_str = f"{speed:.2f} B/s"
                    # Można dodać do loga jeśli potrzeba
            except (ValueError, KeyError):
                pass
        elif d["status"] == "finished":
            self.progress(100, "downloading")

    def transcribe_video(self, filename, language, model_size):
        """Transkrybuje wideo używając Whisper"""
        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")
        
        self.log("Ładowanie modelu Whisper...")

        if DEVICE == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            self.log(f"Używam GPU: {gpu_name}")
        else:
            self.log("UWAGA: GPU nie wykryte! Używam CPU (będzie wolniej).")

        self.progress(0, f"Wczytywanie modelu {model_size} do pamięci ({DEVICE})...")

        try:
            # Persistent internal model cache
            models_dir = os.path.join(os.getcwd(), "models")
            if not os.path.exists(models_dir):
                os.makedirs(models_dir, exist_ok=True)
            self.log(f"Katalog z modelami: {models_dir}")

            model = WhisperModel(model_size, device=DEVICE, compute_type=COMPUTE_TYPE, download_root=models_dir)
            self.current_model = model
        except Exception as e:
            raise Exception(f"Nie można załadować modelu Whisper: {str(e)}")

        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")

        self.log(f"Rozpoczynam transkrypcję (język: {language or 'auto'})...")

        try:
            segments, info = model.transcribe(
                filename,
                language=language,
                beam_size=5,
                vad_filter=True,  # Filtr VAD dla lepszej jakości
            )
            # Konwersja generatora na listę, aby można było po niej iterować wielokrotnie
            segments = list(segments)
        except Exception as e:
            raise Exception(f"Błąd podczas transkrypcji: {str(e)}")

        return segments, info

    def save_transcription(self, segments, info, filename, output_format, language):
        """Zapisuje transkrypcję w wybranym formacie"""
        base_name = os.path.splitext(filename)[0]
        
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

        return output_file

    def _save_txt(self, segments, info, filename, language):
        """Zapisuje transkrypcję w formacie TXT z timestampami"""
        full_text = ""
        with open(filename, "w", encoding="utf-8") as f:
            # Metadane
            detected_lang = getattr(info, 'language', language or 'nieznany')
            lang_prob = getattr(info, 'language_probability', 0.0)
            f.write(f"Język wykryty: {detected_lang} (pewność: {lang_prob:.2%})\n")
            f.write("-" * 40 + "\n\n")

            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                line = f"[{self._format_time(segment.start)} -> {self._format_time(segment.end)}] {segment.text}\n"
                f.write(line)
                full_text += segment.text + " "
                
                if hasattr(info, 'duration') and info.duration > 0:
                    percent = (segment.end / info.duration) * 100
                    self.progress(percent, "transcribing")

        return full_text.strip()

    def _save_txt_no_timestamps(self, segments, info, filename, language):
        """Zapisuje transkrypcję w formacie TXT bez timestampów"""
        full_text = ""
        with open(filename, "w", encoding="utf-8") as f:
            detected_lang = getattr(info, 'language', language or 'nieznany')
            lang_prob = getattr(info, 'language_probability', 0.0)
            f.write(f"Język wykryty: {detected_lang} (pewność: {lang_prob:.2%})\n")
            f.write("-" * 40 + "\n\n")

            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                f.write(segment.text + " ")
                full_text += segment.text + " "
                
                if hasattr(info, 'duration') and info.duration > 0:
                    percent = (segment.end / info.duration) * 100
                    self.progress(percent, "transcribing")

        return full_text.strip()

    def _save_srt(self, segments, filename):
        """Zapisuje transkrypcję w formacie SRT"""
        with open(filename, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                start = self._format_srt_time(segment.start)
                end = self._format_srt_time(segment.end)
                f.write(f"{i}\n{start} --> {end}\n{segment.text}\n\n")
                
                if hasattr(segment, 'duration') and segment.duration > 0:
                    # Progress estimation
                    pass

    def _save_vtt(self, segments, filename):
        """Zapisuje transkrypcję w formacie VTT"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                start = self._format_vtt_time(segment.start)
                end = self._format_vtt_time(segment.end)
                f.write(f"{start} --> {end}\n{segment.text}\n\n")

    def _format_time(self, seconds):
        """Formatuje czas w sekundach do formatu MM:SS"""
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _format_srt_time(self, seconds):
        """Formatuje czas dla SRT"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_vtt_time(self, seconds):
        """Formatuje czas dla VTT"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def check_ollama_status(self):
        """Sprawdza status Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    return True, f"Dostępny ({len(models)} modeli)"
                return True, "Dostępny (brak modeli)"
            return False, "Nie odpowiada"
        except requests.exceptions.RequestException:
            return False, "Niedostępny"

    def get_ollama_models(self):
        """Pobiera listę dostępnych modeli Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                return models
            return []
        except:
            return []

    def summarize_text(self, text, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
        """Generuje podsumowanie tekstu używając Ollama"""
        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")
        
        try:
            self.log("Próba połączenia z Ollama...")
            self.progress(0, "summarizing")

            tags_response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if tags_response.status_code != 200:
                self.log("Ollama nie odpowiada poprawnie.")
                return None

            models = [m["name"] for m in tags_response.json().get("models", [])]
            if not models:
                self.log("Brak modeli w Ollama.")
                return None

            # Wybierz model
            if model_name and model_name in models:
                selected_model = model_name
            else:
                selected_model = models[0]
                for m in models:
                    if "llama3" in m or "mistral" in m:
                        selected_model = m
                        break

            self.log(f"Używam modelu: {selected_model} do podsumowania.")
            self.progress(20, "summarizing")

            # Ogranicz długość tekstu
            text_to_summarize = text[:max_chars]
            if len(text) > max_chars:
                self.log(f"Tekst został obcięty do {max_chars} znaków (oryginał: {len(text)} znaków)")

            # Wybierz prompt na podstawie stylu
            if "Krótkie" in style:
                prompt_text = "Napisz krótkie streszczenie tego tekstu w jednym akapicie (po polsku)"
            elif "Szczegółowe" in style:
                prompt_text = "Sporządź szczegółowe podsumowanie, uwzględniając najważniejsze wątki i detale (po polsku)"
            else:
                prompt_text = "Stwórz zwięzłe podsumowanie w 3 punktach (po polsku)"

            prompt = f"{prompt_text} poniższego tekstu:\n\n{text_to_summarize}"

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": selected_model, "prompt": prompt, "stream": False},
                timeout=300,  # 5 minut timeout
            )

            self.progress(100, "summarizing")

            if response.status_code == 200:
                return response.json().get("response")
            else:
                self.log(f"Błąd Ollama: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            self.log("Timeout przy połączeniu z Ollama (za długo czeka).")
            return None
        except Exception as e:
            self.log(f"Nie udało się połączyć z Ollama: {e}")
            return None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Marcin's YT Downloader & Transcriber v3.1")
        self.root.geometry("800x750")
        
        self.stop_event = threading.Event()
        self.process_thread = None
        self.processor = None
        self.last_output_files = []  # Przechowuje ostatnio utworzone pliki

        self.create_widgets()
        self.check_system_requirements()

    def check_system_requirements(self):
        """Sprawdza wymagania systemowe przy starcie"""
        self.log("Sprawdzanie wymagań systemowych...")
        
        # Sprawdź FFmpeg
        ffmpeg_ok, ffmpeg_msg = VideoProcessor(None, None, None).check_ffmpeg()
        if not ffmpeg_ok:
            self.log(f"⚠️ {ffmpeg_msg}")
            messagebox.showwarning(
                "FFmpeg nie znaleziony",
                "FFmpeg nie jest zainstalowany. Niektóre funkcje mogą nie działać.\n\n"
                "Zainstaluj FFmpeg aby móc konwertować pliki wideo."
            )
        else:
            self.log(f"✓ {ffmpeg_msg}")
        
        # Sprawdź Ollama
        ollama_ok, ollama_msg = VideoProcessor(None, None, None).check_ollama_status()
        if ollama_ok:
            self.log(f"✓ Ollama: {ollama_msg}")
            self.update_ollama_status("available")
        else:
            self.log(f"⚠️ Ollama: {ollama_msg}")
            self.update_ollama_status("unavailable")

    def create_widgets(self):
        # --- SCROLLABLE MAIN FRAME ---
        # Create a main frame to hold the canvas
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Create a canvas
        self.canvas = tk.Canvas(main_container)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a scrollbar to the canvas
        scrollbar = tk.Scrollbar(main_container, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the canvas
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create a frame inside the canvas for the actual content
        main_frame = tk.Frame(self.canvas, padx=10, pady=10)
        
        # Create a window in the canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=main_frame, anchor="nw")

        # Configure scrolling
        main_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        # --- WIDGETS CONTENT ---

        # URL Frame
        url_frame = tk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(url_frame, text="YouTube URL:").pack(anchor="w")
        url_input_frame = tk.Frame(url_frame)
        url_input_frame.pack(fill=tk.X)
        
        self.url_entry = tk.Entry(url_input_frame, width=80)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(0, 5))
        self.url_entry.bind("<KeyRelease>", self.validate_url_on_input)
        
        tk.Button(
            url_input_frame,
            text="Wklej",
            command=self.paste_from_clipboard,
            width=8
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Options Frame
        opts_frame = tk.LabelFrame(main_frame, text="Opcje Pobierania", padx=5, pady=5)
        opts_frame.pack(fill=tk.X, pady=5)

        # Quality and Language row
        row1 = tk.Frame(opts_frame)
        row1.pack(fill=tk.X, pady=2)
        
        tk.Label(row1, text="Jakość:").pack(side=tk.LEFT)
        self.quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(row1, textvariable=self.quality_var, width=12, state="readonly")
        quality_combo["values"] = ("best", "worst", "audio_only")
        quality_combo.pack(side=tk.LEFT, padx=5)
        quality_combo.bind("<<ComboboxSelected>>", self.on_quality_change)

        tk.Label(row1, text="Jakość audio:").pack(side=tk.LEFT, padx=(10, 0))
        self.audio_quality_var = tk.StringVar(value="320")  # Default to highest
        audio_combo = ttk.Combobox(row1, textvariable=self.audio_quality_var, width=8, state="readonly")
        audio_combo["values"] = ("128", "192", "256", "320")
        audio_combo.pack(side=tk.LEFT, padx=5)
        self.audio_quality_combo = audio_combo

        # Path row
        row2 = tk.Frame(opts_frame)
        row2.pack(fill=tk.X, pady=2)
        
        tk.Label(row2, text="Zapisz w:").pack(side=tk.LEFT)
        self.path_entry = tk.Entry(row2)
        self.path_entry.insert(0, os.getcwd())
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(row2, text="...", command=self.browse_folder, width=3).pack(side=tk.LEFT)

        # --- Workflow / AI Options ---
        ai_frame = tk.LabelFrame(main_frame, text="Opcje Przetwarzania AI", padx=5, pady=5)
        ai_frame.pack(fill=tk.X, pady=5)

        row3 = tk.Frame(ai_frame)
        row3.pack(fill=tk.X, pady=2)

        # Checkbox: Transkrybuj
        self.transcribe_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row3,
            text="Transkrybuj (Whisper)",
            variable=self.transcribe_var,
            command=self.on_transcribe_change
        ).pack(side=tk.LEFT)

        tk.Label(row3, text=" | Język:").pack(side=tk.LEFT, padx=(5, 0))
        self.language_var = tk.StringVar(value="Polski")
        lang_combo = ttk.Combobox(row3, textvariable=self.language_var, width=12, state="readonly")
        lang_combo["values"] = tuple(WHISPER_LANGUAGES.keys())
        lang_combo.pack(side=tk.LEFT, padx=5)

        tk.Label(row3, text=" | Model:").pack(side=tk.LEFT, padx=(5, 0))
        self.model_size_var = tk.StringVar(value=DEFAULT_MODEL_SIZE)
        model_combo = ttk.Combobox(row3, textvariable=self.model_size_var, width=10, state="readonly")
        model_combo["values"] = WHISPER_MODELS
        model_combo.pack(side=tk.LEFT, padx=5)
        
        # New Row for Summary
        row4 = tk.Frame(ai_frame)
        row4.pack(fill=tk.X, pady=2)

        self.summarize_var = tk.BooleanVar(value=True)
        self.chk_summarize = tk.Checkbutton(
            row4,
            text="Generuj podsumowanie (Ollama)",
            variable=self.summarize_var,
        )
        self.chk_summarize.pack(side=tk.LEFT)

        tk.Label(row4, text=" | Styl:").pack(side=tk.LEFT, padx=(5, 0))
        self.summary_length_var = tk.StringVar(value="Zwięzłe (3 punkty)")
        summary_combo = ttk.Combobox(row4, textvariable=self.summary_length_var, width=20, state="readonly")
        summary_combo["values"] = ("Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)")
        summary_combo.pack(side=tk.LEFT, padx=5)

        # Ollama status
        self.ollama_status_var = tk.StringVar(value="Sprawdzanie...")
        status_label = tk.Label(row4, textvariable=self.ollama_status_var, fg="gray")
        status_label.pack(side=tk.RIGHT)
        
        # Extra options
        row5 = tk.Frame(ai_frame)
        row5.pack(fill=tk.X, pady=2)

        tk.Label(row5, text="Format transkrypcji:").pack(side=tk.LEFT)
        self.output_format_var = tk.StringVar(value="txt")
        format_combo = ttk.Combobox(row5, textvariable=self.output_format_var, width=15, state="readonly")
        format_combo["values"] = ("txt", "txt_no_timestamps", "srt", "vtt")
        format_combo.pack(side=tk.LEFT, padx=5)

        self.delete_video_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row5,
            text="Usuń wideo po zakończeniu",
            variable=self.delete_video_var,
        ).pack(side=tk.LEFT, padx=(20, 0))

        # --- PROGRESS SECTION ---
        progress_frame = tk.LabelFrame(main_frame, text="Postęp", padx=10, pady=10)
        progress_frame.pack(fill=tk.X, pady=10)

        # Total Progress
        tk.Label(progress_frame, text="Całkowity postęp:").pack(anchor="w")
        self.total_progress_var = tk.DoubleVar()
        self.total_progress_bar = ttk.Progressbar(
            progress_frame, variable=self.total_progress_var, maximum=100
        )
        self.total_progress_bar.pack(fill=tk.X, pady=(0, 10))

        # Task Progress
        self.task_label_var = tk.StringVar(value="Oczekiwanie...")
        tk.Label(progress_frame, textvariable=self.task_label_var).pack(anchor="w")
        self.task_progress_var = tk.DoubleVar()
        self.task_progress_bar = ttk.Progressbar(
            progress_frame, variable=self.task_progress_var, maximum=100
        )
        self.task_progress_bar.pack(fill=tk.X)

        # File size info
        self.file_size_var = tk.StringVar(value="")
        size_label = tk.Label(progress_frame, textvariable=self.file_size_var, fg="blue", font=("Arial", 9))
        size_label.pack(anchor="w", pady=(5, 0))

        # Buttons Frame
        buttons_frame = tk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)

        self.btn_start = tk.Button(
            buttons_frame,
            text="START",
            command=self.start_thread,
            bg="#2196F3",
            fg="white",
            font=("Arial", 12, "bold"),
        )
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_cancel = tk.Button(
            buttons_frame,
            text="ANULUJ",
            command=self.cancel_operation,
            bg="#f44336",
            fg="white",
            font=("Arial", 12, "bold"),
            state="disabled",
        )
        self.btn_cancel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Action buttons (po zakończeniu)
        self.action_buttons_frame = tk.Frame(main_frame)
        self.action_buttons_frame.pack(fill=tk.X, pady=5)
        self.action_buttons_frame.pack_forget()  # Ukryj na początku

        # Logs Frame
        logs_frame = tk.LabelFrame(main_frame, text="Logi", padx=5, pady=5)
        logs_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Logs toolbar
        logs_toolbar = tk.Frame(logs_frame)
        logs_toolbar.pack(fill=tk.X, pady=(0, 5))
        
        tk.Button(
            logs_toolbar,
            text="Wyczyść",
            command=self.clear_logs,
            width=10
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(
            logs_toolbar,
            text="Kopiuj",
            command=self.copy_logs,
            width=10
        ).pack(side=tk.LEFT)

        self.log_text = tk.Text(
            logs_frame, height=12, state="disabled", bg="#f5f5f5", font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def on_frame_configure(self, event):
        """Ustawia region przewijania"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """Dostosowuje szerokość okna wewnętrznego do płótna"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Obsługa kółka myszy"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_transcribe_change(self):
        """Zarządza stanem opcji podsumowania zależnie od transkrypcji"""
        if self.transcribe_var.get():
            self.chk_summarize.config(state="normal")
        else:
            self.summarize_var.set(False)
            self.chk_summarize.config(state="disabled")

    def validate_url_on_input(self, event=None):
        """Waliduje URL podczas wpisywania"""
        url = self.url_entry.get()
        if url.strip():
            is_valid = VideoProcessor(None, None, None).validate_url(url)
            if is_valid:
                self.url_entry.config(bg="white")
            else:
                self.url_entry.config(bg="#ffebee")
        else:
            self.url_entry.config(bg="white")

    def paste_from_clipboard(self):
        """Wkleja URL ze schowka"""
        try:
            clipboard_text = self.root.clipboard_get()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, clipboard_text)
            self.validate_url_on_input()
        except:
            messagebox.showwarning("Błąd", "Nie można wkleić ze schowka")

    def on_quality_change(self, event=None):
        """Aktualizuje dostępność opcji jakości audio"""
        quality = self.quality_var.get()
        if quality == "audio_only":
            self.audio_quality_combo.config(state="readonly")
        else:
            self.audio_quality_combo.config(state="disabled")

    def update_ollama_status(self, status):
        """Aktualizuje wskaźnik statusu Ollama"""
        if status == "available":
            self.ollama_status_var.set("✓ Ollama dostępny")
        else:
            self.ollama_status_var.set("✗ Ollama niedostępny")

    def log(self, message):
        """Thread-safe logging"""
        self.root.after(0, self._log_thread_safe, message)

    def _log_thread_safe(self, message):
        """Thread-safe logging implementation"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def clear_logs(self):
        """Czyści logi"""
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

    def copy_logs(self):
        """Kopiuje logi do schowka"""
        try:
            content = self.log_text.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Sukces", "Logi skopiowane do schowka")
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można skopiować logów: {e}")

    def update_progress(self, percent, stage, file_size=None):
        """Aktualizuje postęp"""
        self.root.after(0, self._progress_thread_safe, percent, stage, file_size)

    def _progress_thread_safe(self, percent, stage, file_size):
        """Thread-safe progress update"""
        # Update Task Bar
        self.task_progress_var.set(percent)

        # Update file size if provided
        if file_size:
            self.file_size_var.set(f"Rozmiar pliku: {file_size}")

        # Calculate Total Progress & Label
        total_percent = 0
        label = ""

        # Adjust total progress weight based on selected tasks
        do_transcribe = self.transcribe_var.get()
        do_summarize = self.summarize_var.get()

        if do_transcribe:
            if do_summarize:
                # DL=33%, TR=33%, SUM=34%
                if stage == "downloading":
                    total_percent = percent * 0.33
                    label = f"Pobieranie wideo... ({percent:.1f}%)"
                elif stage == "transcribing":
                    total_percent = 33 + (percent * 0.33)
                    label = f"Transkrypcja AI... ({percent:.1f}%)"
                elif stage == "summarizing":
                    total_percent = 66 + (percent * 0.34)
                    label = "Generowanie podsumowania..."
            else:
                # DL=50%, TR=50%
                if stage == "downloading":
                    total_percent = percent * 0.50
                    label = f"Pobieranie wideo... ({percent:.1f}%)"
                elif stage == "transcribing":
                    total_percent = 50 + (percent * 0.50)
                    label = f"Transkrypcja AI... ({percent:.1f}%)"
        else:
            # DL=100%
            if stage == "downloading":
                total_percent = percent
                label = f"Pobieranie wideo... ({percent:.1f}%)"

        if stage == "finished":
            total_percent = 100
            label = "Zakończono!"
            self.task_progress_var.set(100)

        self.total_progress_var.set(total_percent)
        self.task_label_var.set(label)

    def browse_folder(self):
        """Otwiera dialog wyboru folderu"""
        d = filedialog.askdirectory(initialdir=self.path_entry.get())
        if d:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, d)

    def open_folder(self, folder_path):
        """Otwiera folder w eksploratorze plików"""
        try:
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można otworzyć folderu: {e}")

    def open_file(self, file_path):
        """Otwiera plik w domyślnej aplikacji"""
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można otworzyć pliku: {e}")

    def show_action_buttons(self, files):
        """Pokazuje przyciski akcji po zakończeniu"""
        # Wyczyść poprzednie przyciski
        for widget in self.action_buttons_frame.winfo_children():
            widget.destroy()
        
        self.last_output_files = files
        
        if files:
            folder = os.path.dirname(files[0]) if files else ""
            
            tk.Button(
                self.action_buttons_frame,
                text="📁 Otwórz folder",
                command=lambda: self.open_folder(folder),
                bg="#4CAF50",
                fg="white",
            ).pack(side=tk.LEFT, padx=5)
            
            for i, file_path in enumerate(files[:3]):  # Maksymalnie 3 przyciski
                file_name = os.path.basename(file_path)
                tk.Button(
                    self.action_buttons_frame,
                    text=f"📄 {file_name[:30]}...",
                    command=lambda f=file_path: self.open_file(f),
                    bg="#FF9800",
                    fg="white",
                ).pack(side=tk.LEFT, padx=5)
        
        self.action_buttons_frame.pack(fill=tk.X, pady=5)

    def hide_action_buttons(self):
        """Ukrywa przyciski akcji"""
        self.action_buttons_frame.pack_forget()

    def cancel_operation(self):
        """Anuluje bieżącą operację"""
        if messagebox.askyesno("Anuluj", "Czy na pewno chcesz anulować operację?"):
            self.stop_event.set()
            self.log("Anulowanie operacji...")
            self.btn_cancel.config(state="disabled")

    def start_thread(self):
        """Uruchamia proces w osobnym wątku"""
        if self.process_thread and self.process_thread.is_alive():
            messagebox.showwarning("Uwaga", "Operacja już trwa!")
            return
        
        self.stop_event.clear()
        self.hide_action_buttons()
        self.process_thread = threading.Thread(target=self.run_process, daemon=True)
        self.process_thread.start()

    def run_process(self):
        """Główna funkcja przetwarzania"""
        url = self.url_entry.get().strip()
        path = self.path_entry.get().strip()
        quality = self.quality_var.get()
        audio_quality = self.audio_quality_var.get() if quality == "audio_only" else "192"
        language_name = self.language_var.get()
        language = WHISPER_LANGUAGES.get(language_name)
        model_size = self.model_size_var.get()
        output_format = self.output_format_var.get()
        
        # New options
        do_transcribe = self.transcribe_var.get()
        do_summarize = self.summarize_var.get()
        summary_style = self.summary_length_var.get()

        # Walidacja URL
        processor = VideoProcessor(self.log, self.update_progress, self.stop_event)
        if not processor.validate_url(url):
            self.root.after(0, lambda: messagebox.showerror("Błąd", "Nieprawidłowy URL YouTube!"))
            return

        # Walidacja ścieżki
        path_ok, path_msg = processor.validate_path(path)
        if not path_ok:
            self.root.after(0, lambda: messagebox.showerror("Błąd", path_msg))
            return

        # Sprawdź miejsce na dysku
        disk_ok, disk_msg = processor.check_disk_space(path)
        if not disk_ok:
            if not messagebox.askyesno("Ostrzeżenie", f"{disk_msg}\n\nKontynuować mimo to?"):
                return
        else:
            self.log(f"✓ {disk_msg}")

        # Sprawdź czy plik może już istnieć (ostrzeżenie)
        # To będzie sprawdzone podczas pobierania

        # Aktualizuj UI
        self.root.after(0, lambda: self.btn_start.config(state="disabled"))
        self.root.after(0, lambda: self.btn_cancel.config(state="normal"))
        self.log("Start procesu...")
        self.update_progress(0, "downloading")

        video_file = None
        txt_file = None
        summary_file = None

        try:
            # 1. Download
            if self.stop_event.is_set():
                raise InterruptedError("Anulowano")
            
            video_file = processor.download_video(url, path, quality, audio_quality)
            
            # Sprawdź czy plik istnieje i czy jest duplikat
            if os.path.exists(video_file):
                file_size = processor.get_file_size(video_file)
                self.log(f"Pobrano: {os.path.basename(video_file)} ({file_size})")
                self.update_progress(100, "downloading", file_size)
            else:
                raise Exception("Plik nie został pobrany poprawnie")

            # 2. Transcribe (If enabled)
            if do_transcribe:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                segments, info = processor.transcribe_video(video_file, language, model_size)
                
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                txt_file = processor.save_transcription(
                    segments, info, video_file, output_format, language
                )
                self.log(f"Transkrypcja zapisana: {os.path.basename(txt_file)}")

                # 3. Summarize (If enabled + transcribtion done)
                if do_summarize and not self.stop_event.is_set():
                    # Pobierz pełny tekst z transkrypcji
                    full_text = ""
                    for segment in segments:
                        full_text += segment.text + " "
                    
                    ollama_models = processor.get_ollama_models()
                    model_name = ollama_models[0] if ollama_models else None
                    
                    summary = processor.summarize_text(full_text.strip(), model_name, style=summary_style)
                    if summary:
                        summary_file = os.path.splitext(video_file)[0] + "_podsumowanie.txt"
                        with open(summary_file, "w", encoding="utf-8") as f:
                            f.write(summary)
                        self.log(f"Podsumowanie zapisane: {os.path.basename(summary_file)}")
                        self.log("--- PODSUMOWANIE ---")
                        self.log(summary)
                        self.log("--------------------")
                    else:
                        self.log("Nie udało się wygenerować podsumowania")
            else:
                self.log("Transkrypcja i podsumowanie pominięte (odznaczone).")

            # 4. Usuń wideo jeśli zaznaczono
            if self.delete_video_var.get() and video_file and os.path.exists(video_file):
                try:
                    os.remove(video_file)
                    self.log(f"Usunięto plik wideo: {os.path.basename(video_file)}")
                except Exception as e:
                    self.log(f"Nie można usunąć pliku wideo: {e}")

            # Sukces
            output_files = [f for f in [video_file, txt_file, summary_file] if f and os.path.exists(f)]
            self.root.after(0, lambda: self.show_action_buttons(output_files))
            self.root.after(0, lambda: messagebox.showinfo("Sukces", "Zakończono pomyślnie!"))
            self.update_progress(100, "finished")

        except InterruptedError:
            self.log("Operacja anulowana przez użytkownika")
            logging.info("Operacja anulowana przez użytkownika")
            if video_file and os.path.exists(video_file):
                try:
                    os.remove(video_file)
                except:
                    pass
            self.root.after(0, lambda: messagebox.showinfo("Anulowano", "Operacja została anulowana"))
        except Exception as e:
            error_msg = f"{str(e)}"
            self.log(f"BŁĄD: {error_msg}")
            logging.error("Wystąpił nieoczekiwany błąd w wątku przetwarzania", exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("Błąd", f"Wystąpił błąd:\n{error_msg}\n\nSzczegóły w pliku app_debug.log"))
        finally:
            self.root.after(0, lambda: self.btn_start.config(state="normal"))
            self.root.after(0, lambda: self.btn_cancel.config(state="disabled"))
            self.update_progress(0, "finished")


if __name__ == "__main__":
    # Konfiguracja logowania
    logging.basicConfig(
        filename="app_debug.log",
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8"
    )
    logging.info("Aplikacja uruchomiona")

    root = tk.Tk()
    app = App(root)
    root.mainloop()
