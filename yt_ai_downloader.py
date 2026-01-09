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
            return True, "Nie można sprawdzić miejsca"

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
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
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

    def convert_to_mp3(self, input_path, output_path=None):
        """Konwertuje plik audio do MP3 używając FFmpeg"""
        if self.stop_event.is_set():
            raise InterruptedError("Anulowano")

        if not output_path:
            base, _ = os.path.splitext(input_path)
            output_path = base + ".mp3"

        self.log(f"Konwersja do MP3: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        self.progress(0, "converting")

        try:
            # Używamy ffmpeg do konwersji
            cmd = [
                "ffmpeg", "-y",  # Nadpisz jeśli istnieje
                "-loglevel", "error", "-nostats",  # Fix buffer overflow
                "-i", input_path,
                "-codec:a", "libmp3lame",
                "-qscale:a", "2",  # Dobra jakość VBR (~190kbps)
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            
            # Czekamy na zakończenie, sprawdzając stop_event
            while process.poll() is None:
                if self.stop_event.is_set():
                    process.terminate()
                    raise InterruptedError("Anulowano konwersję")
                time.sleep(0.1)
            
            if process.returncode != 0:
                _, stderr = process.communicate()
                raise Exception(f"Błąd FFmpeg: {stderr}")

            self.progress(100, "converting")
            return output_path

        except Exception as e:
            raise Exception(f"Błąd konwersji: {str(e)}")

    def download_video(self, url, save_path, quality, audio_quality="192"):
        """Pobiera wideo z YouTube"""
        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")
        
        self.log(f"Pobieranie wideo ({quality})...")
        self.progress(0, "downloading")

        common_opts = {
            "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"),
            "progress_hooks": [self.yt_dlp_hook],
            "writethumbnail": False,
            "writeinfojson": False,
            "keepvideo": False,
            "noplaylist": True,
            "socket_timeout": 30,
        }

        if quality == "best":
            ydl_opts = {
                **common_opts,
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            }
        elif quality == "worst":
            ydl_opts = {
                **common_opts,
                "format": "worst",
                "merge_output_format": "mp4",
                "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            }
        elif quality == "audio_only":
            ydl_opts = {
                **common_opts,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }],
            }

        filename = ""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                base = os.path.splitext(filename)[0]
                if quality == "audio_only":
                    filename = base + ".mp3"
                else:
                    filename = base + ".mp4"
                
                if os.path.exists(filename):
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
            except (ValueError, KeyError):
                pass
        elif d["status"] == "finished":
            self.progress(100, "downloading")

    def transcribe_video(self, filename, language, model_size):
        """Transkrybuje plik używając Whisper"""
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
                vad_filter=True,
            )
            segments = list(segments)
        except Exception as e:
            raise Exception(f"Błąd podczas transkrypcji: {str(e)}")

        return segments, info

    def save_transcription(self, segments, info, filename, output_format, language):
        """Zapisuje transkrypcję"""
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
        full_text = ""
        with open(filename, "w", encoding="utf-8") as f:
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
        with open(filename, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                start = self._format_srt_time(segment.start)
                end = self._format_srt_time(segment.end)
                f.write(f"{i}\n{start} --> {end}\n{segment.text}\n\n")

    def _save_vtt(self, segments, filename):
        with open(filename, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for segment in segments:
                if self.stop_event.is_set():
                    raise InterruptedError("Anulowano")
                
                start = self._format_vtt_time(segment.start)
                end = self._format_vtt_time(segment.end)
                f.write(f"{start} --> {end}\n{segment.text}\n\n")

    def _format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _format_srt_time(self, seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_vtt_time(self, seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def check_ollama_status(self):
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
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                return models
            return []
        except:
            return []

    def summarize_text(self, text, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
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

            text_to_summarize = text[:max_chars]
            if len(text) > max_chars:
                self.log(f"Tekst został obcięty do {max_chars} znaków")

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
                timeout=300,
            )

            self.progress(100, "summarizing")

            if response.status_code == 200:
                return response.json().get("response")
            else:
                self.log(f"Błąd Ollama: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            self.log("Timeout przy połączeniu z Ollama.")
            return None
        except Exception as e:
            self.log(f"Nie udało się połączyć z Ollama: {e}")
            return None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Marcin's YT & Local Media Transcriber v3.2")
        self.root.geometry("800x800")
        
        self.stop_event = threading.Event()
        self.process_thread = None
        self.last_output_files = []

        self.create_widgets()
        self.check_system_requirements()

    def check_system_requirements(self):
        self.log("Sprawdzanie wymagań systemowych...")
        
        ffmpeg_ok, ffmpeg_msg = VideoProcessor(None, None, None).check_ffmpeg()
        if not ffmpeg_ok:
            self.log(f"⚠️ {ffmpeg_msg}")
            messagebox.showwarning(
                "FFmpeg nie znaleziony",
                "FFmpeg nie jest zainstalowany. Transkrypcja i konwersja plików nie będą działać."
            )
        else:
            self.log(f"✓ {ffmpeg_msg}")
        
        ollama_ok, ollama_msg = VideoProcessor(None, None, None).check_ollama_status()
        if ollama_ok:
            self.log(f"✓ Ollama: {ollama_msg}")
            self.update_ollama_status("available")
        else:
            self.log(f"⚠️ Ollama: {ollama_msg}")
            self.update_ollama_status("unavailable")

    def create_widgets(self):
        # --- MAIN CONTAINER ---
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_container)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(main_container, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        main_frame = tk.Frame(self.canvas, padx=10, pady=10)
        self.canvas_window = self.canvas.create_window((0, 0), window=main_frame, anchor="nw")

        main_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        # --- TABS (NOTEBOOK) ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.X, pady=(0, 10))

        # Tab 1: YouTube
        self.tab_yt = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(self.tab_yt, text="YouTube")

        # Tab 2: Lokalne Pliki
        self.tab_local = tk.Frame(self.notebook, padx=10, pady=10)
        self.notebook.add(self.tab_local, text="Pliki Lokalne (Pixel/Audio)")

        # --- CONTENT OF TAB 1: YOUTUBE ---
        yt_url_frame = tk.Frame(self.tab_yt)
        yt_url_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(yt_url_frame, text="YouTube URL:").pack(anchor="w")
        yt_input_frame = tk.Frame(yt_url_frame)
        yt_input_frame.pack(fill=tk.X)
        
        self.url_entry = tk.Entry(yt_input_frame, width=80)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(0, 5))
        self.url_entry.bind("<KeyRelease>", self.validate_url_on_input)
        
        tk.Button(yt_input_frame, text="Wklej", command=self.paste_from_clipboard, width=8).pack(side=tk.LEFT, padx=(5, 0))

        # YouTube Options
        yt_opts_frame = tk.LabelFrame(self.tab_yt, text="Opcje Pobierania", padx=5, pady=5)
        yt_opts_frame.pack(fill=tk.X, pady=5)

        row1 = tk.Frame(yt_opts_frame)
        row1.pack(fill=tk.X, pady=2)
        
        tk.Label(row1, text="Jakość:").pack(side=tk.LEFT)
        self.quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(row1, textvariable=self.quality_var, width=12, state="readonly")
        quality_combo["values"] = ("best", "worst", "audio_only")
        quality_combo.pack(side=tk.LEFT, padx=5)
        quality_combo.bind("<<ComboboxSelected>>", self.on_quality_change)

        tk.Label(row1, text="Jakość audio:").pack(side=tk.LEFT, padx=(10, 0))
        self.audio_quality_var = tk.StringVar(value="320")
        self.audio_quality_combo = ttk.Combobox(row1, textvariable=self.audio_quality_var, width=8, state="readonly")
        self.audio_quality_combo["values"] = ("128", "192", "256", "320")
        self.audio_quality_combo.pack(side=tk.LEFT, padx=5)

        # --- CONTENT OF TAB 2: LOCAL FILES ---
        local_frame = tk.Frame(self.tab_local)
        local_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(local_frame, text="Wybierz plik audio/wideo:").pack(anchor="w")
        
        file_input_frame = tk.Frame(local_frame)
        file_input_frame.pack(fill=tk.X)

        self.local_file_entry = tk.Entry(file_input_frame, width=70)
        self.local_file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(file_input_frame, text="Przeglądaj...", command=self.browse_local_file).pack(side=tk.LEFT, padx=5)

        # Local Options
        local_opts_frame = tk.LabelFrame(self.tab_local, text="Opcje Lokalne", padx=5, pady=5)
        local_opts_frame.pack(fill=tk.X, pady=5)

        self.convert_mp3_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            local_opts_frame, 
            text="Konwertuj na MP3 przed transkrypcją (Zalecane dla nagrań z Pixela/m4a)",
            variable=self.convert_mp3_var
        ).pack(anchor="w")

        # --- COMMON SECTION (BELOW TABS) ---
        
        # Path Row (Common output folder)
        path_frame = tk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=5)
        tk.Label(path_frame, text="Folder zapisu (wyniki):").pack(side=tk.LEFT)
        self.path_entry = tk.Entry(path_frame)
        self.path_entry.insert(0, os.getcwd())
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(path_frame, text="...", command=self.browse_folder, width=3).pack(side=tk.LEFT)

        # AI Options
        ai_frame = tk.LabelFrame(main_frame, text="Opcje Przetwarzania AI (Wspólne)", padx=5, pady=5)
        ai_frame.pack(fill=tk.X, pady=5)

        row3 = tk.Frame(ai_frame)
        row3.pack(fill=tk.X, pady=2)

        self.transcribe_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row3, text="Transkrybuj (Whisper)", variable=self.transcribe_var, command=self.on_transcribe_change).pack(side=tk.LEFT)

        tk.Label(row3, text=" | Język:").pack(side=tk.LEFT, padx=(5, 0))
        self.language_var = tk.StringVar(value="Polski")
        ttk.Combobox(row3, textvariable=self.language_var, values=tuple(WHISPER_LANGUAGES.keys()), width=12, state="readonly").pack(side=tk.LEFT, padx=5)

        tk.Label(row3, text=" | Model:").pack(side=tk.LEFT, padx=(5, 0))
        self.model_size_var = tk.StringVar(value=DEFAULT_MODEL_SIZE)
        ttk.Combobox(row3, textvariable=self.model_size_var, values=WHISPER_MODELS, width=10, state="readonly").pack(side=tk.LEFT, padx=5)
        
        row4 = tk.Frame(ai_frame)
        row4.pack(fill=tk.X, pady=2)

        self.summarize_var = tk.BooleanVar(value=True)
        self.chk_summarize = tk.Checkbutton(row4, text="Generuj podsumowanie (Ollama)", variable=self.summarize_var)
        self.chk_summarize.pack(side=tk.LEFT)

        tk.Label(row4, text=" | Styl:").pack(side=tk.LEFT, padx=(5, 0))
        self.summary_length_var = tk.StringVar(value="Zwięzłe (3 punkty)")
        ttk.Combobox(row4, textvariable=self.summary_length_var, values=("Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)"), width=20, state="readonly").pack(side=tk.LEFT, padx=5)

        self.ollama_status_var = tk.StringVar(value="Sprawdzanie...")
        tk.Label(row4, textvariable=self.ollama_status_var, fg="gray").pack(side=tk.RIGHT)
        
        row5 = tk.Frame(ai_frame)
        row5.pack(fill=tk.X, pady=2)
        tk.Label(row5, text="Format transkrypcji:").pack(side=tk.LEFT)
        self.output_format_var = tk.StringVar(value="txt")
        ttk.Combobox(row5, textvariable=self.output_format_var, values=("txt", "txt_no_timestamps", "srt", "vtt"), width=15, state="readonly").pack(side=tk.LEFT, padx=5)

        self.delete_video_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row5, text="Usuń plik źródłowy po zakończeniu (Tylko pobrane)", variable=self.delete_video_var).pack(side=tk.LEFT, padx=(20, 0))

        # Progress
        progress_frame = tk.LabelFrame(main_frame, text="Postęp", padx=10, pady=10)
        progress_frame.pack(fill=tk.X, pady=10)

        tk.Label(progress_frame, text="Całkowity postęp:").pack(anchor="w")
        self.total_progress_var = tk.DoubleVar()
        self.total_progress_bar = ttk.Progressbar(progress_frame, variable=self.total_progress_var, maximum=100)
        self.total_progress_bar.pack(fill=tk.X, pady=(0, 10))

        self.task_label_var = tk.StringVar(value="Oczekiwanie...")
        tk.Label(progress_frame, textvariable=self.task_label_var).pack(anchor="w")
        self.task_progress_var = tk.DoubleVar()
        self.task_progress_bar = ttk.Progressbar(progress_frame, variable=self.task_progress_var, maximum=100)
        self.task_progress_bar.pack(fill=tk.X)

        self.file_size_var = tk.StringVar(value="")
        tk.Label(progress_frame, textvariable=self.file_size_var, fg="blue", font=("Arial", 9)).pack(anchor="w", pady=(5, 0))

        # Buttons
        buttons_frame = tk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)

        self.btn_start = tk.Button(buttons_frame, text="START", command=self.start_thread, bg="#2196F3", fg="white", font=("Arial", 12, "bold"))
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_cancel = tk.Button(buttons_frame, text="ANULUJ", command=self.cancel_operation, bg="#f44336", fg="white", font=("Arial", 12, "bold"), state="disabled")
        self.btn_cancel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        self.action_buttons_frame = tk.Frame(main_frame)
        self.action_buttons_frame.pack(fill=tk.X, pady=5)
        self.action_buttons_frame.pack_forget()

        # Logs
        logs_frame = tk.LabelFrame(main_frame, text="Logi", padx=5, pady=5)
        logs_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        logs_toolbar = tk.Frame(logs_frame)
        logs_toolbar.pack(fill=tk.X, pady=(0, 5))
        tk.Button(logs_toolbar, text="Wyczyść", command=self.clear_logs, width=10).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(logs_toolbar, text="Kopiuj", command=self.copy_logs, width=10).pack(side=tk.LEFT)

        self.log_text = tk.Text(logs_frame, height=12, state="disabled", bg="#f5f5f5", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # --- EVENT HANDLERS ---
    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_transcribe_change(self):
        if self.transcribe_var.get():
            self.chk_summarize.config(state="normal")
        else:
            self.summarize_var.set(False)
            self.chk_summarize.config(state="disabled")

    def validate_url_on_input(self, event=None):
        url = self.url_entry.get()
        if url.strip():
            is_valid = VideoProcessor(None, None, None).validate_url(url)
            self.url_entry.config(bg="white" if is_valid else "#ffebee")
        else:
            self.url_entry.config(bg="white")

    def paste_from_clipboard(self):
        try:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, self.root.clipboard_get())
            self.validate_url_on_input()
        except:
            pass

    def browse_local_file(self):
        f = filedialog.askopenfilename(filetypes=[("Audio/Video", "*.mp4 *.mp3 *.m4a *.wav *.mkv *.avi"), ("Wszystkie pliki", "*.*")])
        if f:
            self.local_file_entry.delete(0, tk.END)
            self.local_file_entry.insert(0, f)

    def on_quality_change(self, event=None):
        if self.quality_var.get() == "audio_only":
            self.audio_quality_combo.config(state="readonly")
        else:
            self.audio_quality_combo.config(state="disabled")

    def update_ollama_status(self, status):
        self.ollama_status_var.set("✓ Ollama dostępny" if status == "available" else "✗ Ollama niedostępny")

    def log(self, message):
        self.root.after(0, self._log_thread_safe, message)

    def _log_thread_safe(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

    def copy_logs(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_text.get(1.0, tk.END))
        messagebox.showinfo("Sukces", "Logi skopiowane")

    def update_progress(self, percent, stage, file_size=None):
        self.root.after(0, self._progress_thread_safe, percent, stage, file_size)

    def _progress_thread_safe(self, percent, stage, file_size):
        self.task_progress_var.set(percent)
        if file_size:
            self.file_size_var.set(f"Rozmiar pliku: {file_size}")

        total_percent = 0
        label = ""
        do_transcribe = self.transcribe_var.get()
        do_summarize = self.summarize_var.get()
        
        # Stages: downloading, converting, transcribing, summarizing
        # Simplified progress logic
        weights = {}
        if self.notebook.index(self.notebook.select()) == 0: # YouTube tab
            if do_transcribe:
                weights = {'downloading': 40, 'transcribing': 40, 'summarizing': 20} if do_summarize else {'downloading': 50, 'transcribing': 50}
            else:
                weights = {'downloading': 100}
        else: # Local tab
            has_conversion = self.convert_mp3_var.get()
            if has_conversion:
                 weights = {'converting': 20, 'transcribing': 60, 'summarizing': 20} if do_summarize else {'converting': 30, 'transcribing': 70}
            else:
                 weights = {'transcribing': 70, 'summarizing': 30} if do_summarize else {'transcribing': 100}

        current_base = 0
        # Quick and dirty progress mapping based on stage name
        if stage == "downloading":
            max_w = weights.get('downloading', 0)
            total_percent = (percent / 100) * max_w
            label = f"Pobieranie... {percent:.1f}%"
        elif stage == "converting":
            base = weights.get('downloading', 0)
            max_w = weights.get('converting', 0)
            total_percent = base + ((percent/100) * max_w)
            label = f"Konwersja MP3... {percent:.1f}%"
        elif stage == "transcribing":
            base = weights.get('downloading', 0) + weights.get('converting', 0)
            max_w = weights.get('transcribing', 0)
            total_percent = base + ((percent/100) * max_w)
            label = f"Transkrypcja AI... {percent:.1f}%"
        elif stage == "summarizing":
            base = weights.get('downloading', 0) + weights.get('converting', 0) + weights.get('transcribing', 0)
            max_w = weights.get('summarizing', 0)
            total_percent = base + ((percent/100) * max_w)
            label = "Generowanie podsumowania..."
        elif stage == "finished":
            total_percent = 100
            label = "Zakończono!"

        self.total_progress_var.set(total_percent)
        self.task_label_var.set(label)

    def browse_folder(self):
        d = filedialog.askdirectory(initialdir=self.path_entry.get())
        if d:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, d)

    def open_folder(self, folder_path):
        try:
            if platform.system() == "Windows": os.startfile(folder_path)
            elif platform.system() == "Darwin": subprocess.run(["open", folder_path])
            else: subprocess.run(["xdg-open", folder_path])
        except: pass

    def open_file(self, file_path):
        try:
            if platform.system() == "Windows": os.startfile(file_path)
            elif platform.system() == "Darwin": subprocess.run(["open", file_path])
            else: subprocess.run(["xdg-open", file_path])
        except: pass

    def show_action_buttons(self, files):
        for widget in self.action_buttons_frame.winfo_children():
            widget.destroy()
        if files:
            folder = os.path.dirname(files[0])
            tk.Button(self.action_buttons_frame, text="📁 Folder", command=lambda: self.open_folder(folder), bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
            for file_path in files[:3]:
                tk.Button(self.action_buttons_frame, text=f"📄 {os.path.basename(file_path)[:20]}...", command=lambda f=file_path: self.open_file(f), bg="#FF9800", fg="white").pack(side=tk.LEFT, padx=5)
        self.action_buttons_frame.pack(fill=tk.X, pady=5)

    def hide_action_buttons(self):
        self.action_buttons_frame.pack_forget()

    def cancel_operation(self):
        if messagebox.askyesno("Anuluj", "Przerwać operację?"):
            self.stop_event.set()
            self.btn_cancel.config(state="disabled")

    def start_thread(self):
        if self.process_thread and self.process_thread.is_alive(): return
        self.stop_event.clear()
        self.hide_action_buttons()
        self.process_thread = threading.Thread(target=self.run_process, daemon=True)
        self.process_thread.start()

    def run_process(self):
        # Pobieranie danych z GUI
        save_path = self.path_entry.get().strip()
        quality = self.quality_var.get()
        audio_quality = self.audio_quality_var.get()
        language = WHISPER_LANGUAGES.get(self.language_var.get())
        model_size = self.model_size_var.get()
        output_format = self.output_format_var.get()
        
        do_transcribe = self.transcribe_var.get()
        do_summarize = self.summarize_var.get()
        summary_style = self.summary_length_var.get()
        
        # Sprawdzenie która zakładka jest aktywna
        current_tab_index = self.notebook.index(self.notebook.select())
        is_youtube_mode = (current_tab_index == 0)
        
        processor = VideoProcessor(self.log, self.update_progress, self.stop_event)
        
        # Walidacja ścieżki zapisu
        path_ok, path_msg = processor.validate_path(save_path)
        if not path_ok:
            self.root.after(0, lambda: messagebox.showerror("Błąd", path_msg))
            return

        self.root.after(0, lambda: self.btn_start.config(state="disabled"))
        self.root.after(0, lambda: self.btn_cancel.config(state="normal"))
        self.log(f"Start w trybie: {'YouTube' if is_youtube_mode else 'Plik Lokalny'}")

        video_file = None
        txt_file = None
        summary_file = None

        try:
            # 1. Pozyskanie pliku źródłowego (Download lub Select)
            if is_youtube_mode:
                url = self.url_entry.get().strip()
                if not processor.validate_url(url):
                    raise Exception("Nieprawidłowy URL YouTube")
                video_file = processor.download_video(url, save_path, quality, audio_quality)
            else:
                local_path = self.local_file_entry.get().strip()
                if not os.path.exists(local_path):
                    raise Exception("Wybrany plik lokalny nie istnieje")
                
                # Opcjonalna konwersja do MP3
                if self.convert_mp3_var.get():
                    # Utwórz nazwę pliku wynikowego w folderze docelowym
                    filename = os.path.basename(local_path)
                    target_mp3 = os.path.join(save_path, os.path.splitext(filename)[0] + ".mp3")
                    video_file = processor.convert_to_mp3(local_path, target_mp3)
                else:
                    video_file = local_path # Użyj oryginału

            # 2. Transkrypcja
            if do_transcribe and video_file:
                segments, info = processor.transcribe_video(video_file, language, model_size)
                # Zapisujemy w folderze wyjściowym (save_path)
                # Jeśli plik wideo jest gdzie indziej, musimy zbudować ścieżkę dla txt
                base_name = os.path.basename(video_file)
                output_base = os.path.join(save_path, base_name)
                
                txt_file = processor.save_transcription(segments, info, output_base, output_format, language)
                self.log(f"Transkrypcja: {os.path.basename(txt_file)}")

                # 3. Podsumowanie
                if do_summarize:
                    full_text = " ".join([s.text for s in segments])
                    summary = processor.summarize_text(full_text.strip(), style=summary_style)
                    if summary:
                        summary_file = os.path.splitext(output_base)[0] + "_podsumowanie.txt"
                        with open(summary_file, "w", encoding="utf-8") as f: f.write(summary)
                        self.log(f"Podsumowanie: {os.path.basename(summary_file)}")
            
            # 4. Sprzątanie (tylko dla YouTube, plików lokalnych nie usuwamy)
            if is_youtube_mode and self.delete_video_var.get() and video_file:
                 try: os.remove(video_file)
                 except: pass

            output_files = [f for f in [video_file, txt_file, summary_file] if f and os.path.exists(f)]
            self.root.after(0, lambda: self.show_action_buttons(output_files))
            self.root.after(0, lambda: messagebox.showinfo("Sukces", "Zakończono!"))
            self.update_progress(100, "finished")

        except InterruptedError:
            self.log("Anulowano przez użytkownika")
        except Exception as e:
            self.log(f"BŁĄD: {e}")
            self.root.after(0, lambda: messagebox.showerror("Błąd", str(e)))
        finally:
            self.root.after(0, lambda: self.btn_start.config(state="normal"))
            self.root.after(0, lambda: self.btn_cancel.config(state="disabled"))
            self.update_progress(0, "finished")

if __name__ == "__main__":
    logging.basicConfig(filename="app_debug.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    root = tk.Tk()
    app = App(root)
    root.mainloop()

