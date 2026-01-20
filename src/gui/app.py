import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import threading
import time
import platform
import subprocess
import logging

from src.core.processor import Processor
from src.utils.logger import Logger
from src.utils.config import WHISPER_LANGUAGES, WHISPER_MODELS, DEFAULT_MODEL_SIZE
from src.utils.helpers import check_ffmpeg

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Marcin's YT & Local Media Transcriber v3.2")
        self.root.geometry("800x800")
        
        self.stop_event = threading.Event()
        self.process_thread = None
        self.stop_event = threading.Event()
        self.process_thread = None
        self.last_output_files = []
        self.batch_info = (0, 0) # current, total
        
        # Internal logger helper
        self.logger = Logger(self._log_thread_safe)

        self.create_widgets()
        self.check_system_requirements()

    def check_system_requirements(self):
        self.log("Sprawdzanie wymagań systemowych...")
        
        ffmpeg_ok, ffmpeg_msg = check_ffmpeg()
        if not ffmpeg_ok:
            self.log(f"⚠️ {ffmpeg_msg}")
            messagebox.showwarning(
                "FFmpeg nie znaleziony",
                "FFmpeg nie jest zainstalowany. Transkrypcja i konwersja plików nie będą działać."
            )
        else:
            self.log(f"✓ {ffmpeg_msg}")
        
        # Use a temporary processor to check status
        temp_processor = Processor(None, None, None)
        ollama_ok, ollama_msg = temp_processor.check_ollama_status()
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
        # Use simple Processor wrapper for validation
        if url.strip():
            # For pure validation we can use helpers directly inside App too, but cleaner via Processor maybe?
            # Actually, helpers is cleaner for static checks.
            # But the original code used VideoProcessor.validate_url
            temp_processor = Processor(None, None, None)
            is_valid = temp_processor.validate_url(url)
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
         # Call logger helper
         self.logger.log(message)

    def _log_thread_safe(self, message):
        self.log_text.config(state="normal")
        # Ensure timestamp is not duplicated if logger adds it (logger format has it, but text widget inserts manually in original)
        # Original: f"[{time.strftime('%H:%M:%S')}] {message}\n"
        # My logger.py does logging.info(message), but the callback receives raw message?
        # Let's check logger.py... it calls self.log_callback(message).
        # So I should format it here.
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

        # Calculate progress for current file
        file_percent = 0
        if stage == "downloading":
            max_w = weights.get('downloading', 0)
            file_percent = (percent / 100) * max_w
            label = f"Pobieranie... {percent:.1f}%"
        elif stage == "converting":
            base = weights.get('downloading', 0)
            max_w = weights.get('converting', 0)
            file_percent = base + ((percent/100) * max_w)
            label = f"Konwersja MP3... {percent:.1f}%"
        elif stage == "transcribing":
            base = weights.get('downloading', 0) + weights.get('converting', 0)
            max_w = weights.get('transcribing', 0)
            file_percent = base + ((percent/100) * max_w)
            label = f"Transkrypcja AI... {percent:.1f}%"
        elif stage == "summarizing":
            base = weights.get('downloading', 0) + weights.get('converting', 0) + weights.get('transcribing', 0)
            max_w = weights.get('summarizing', 0)
            file_percent = base + ((percent/100) * max_w)
            label = "Generowanie podsumowania..."
        elif stage == "finished":
            file_percent = 100
            label = "Zakończono!"

        # Calculate total batch progress
        current, total = self.batch_info
        if total > 1:
            # Scale file_percent to batch item slot
            item_slot = 100 / total
            total_batch_percent = ((current - 1) * item_slot) + (file_percent / 100 * item_slot)
            
            label = f"[{current}/{total}] {label}"
            self.total_progress_var.set(total_batch_percent)
        else:
            self.total_progress_var.set(file_percent)

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
        # Ensure we don't hold references to old thread? (standard threading)
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
        
        # Create processor instance
        # Note: we pass self.logger (wrapper) so we need to ensure Processor uses it correctly.
        # Processor calls logger.log(msg). My Logger.log calls logging.info and callback.
        # Perfect.
        processor = Processor(self.logger, self.stop_event, self.update_progress)
        
        # Walidacja ścieżki zapisu
        path_ok, path_msg = processor.validate_path(save_path)
        if not path_ok:
            self.root.after(0, lambda: messagebox.showerror("Błąd", path_msg))
            return

        self.root.after(0, lambda: self.btn_start.config(state="disabled"))
        self.root.after(0, lambda: self.btn_cancel.config(state="normal"))
        self.log(f"Start w trybie: {'YouTube' if is_youtube_mode else 'Plik Lokalny'}")
        
        # Reset batch info
        self.batch_info = (0, 0)
        video_files = []
        all_output_files = []

        try:
            # 1. Pozyskanie plików źródłowych
            if is_youtube_mode:
                url = self.url_entry.get().strip()
                if not processor.validate_url(url):
                    raise Exception("Nieprawidłowy URL YouTube")
                # Zwraca LISTĘ plików
                video_files = processor.download_video(url, save_path, quality, audio_quality)
            else:
                local_path = self.local_file_entry.get().strip()
                if not os.path.exists(local_path):
                    raise Exception("Wybrany plik lokalny nie istnieje")
                
                final_local_file = local_path
                # Opcjonalna konwersja do MP3
                if self.convert_mp3_var.get():
                    filename = os.path.basename(local_path)
                    target_mp3 = os.path.join(save_path, os.path.splitext(filename)[0] + ".mp3")
                    final_local_file = processor.convert_to_mp3(local_path, target_mp3)
                
                video_files = [final_local_file]

            # Ustawienie info o batchu
            self.batch_info = (0, len(video_files))
            total_files = len(video_files)
            
            # 2. Przetwarzanie sekwencyjne
            for i, video_file in enumerate(video_files, 1):
                if self.stop_event.is_set():
                    break
                    
                self.batch_info = (i, total_files)
                # Resetujemy postęp pliku
                self.update_progress(0, "transcribing" if do_transcribe else "finished")
                
                all_output_files.append(video_file)
                base_name = os.path.basename(video_file)

                # Transkrypcja
                txt_file = None
                if do_transcribe:
                    self.log(f"[{i}/{total_files}] Przetwarzanie: {base_name}")
                    segments, info = processor.transcribe_video(video_file, language, model_size)
                    
                    output_base = os.path.join(save_path, base_name)
                    txt_file = processor.save_transcription(segments, info, output_base, output_format, language)
                    all_output_files.append(txt_file)
                    self.log(f"Transkrypcja gotowa: {os.path.basename(txt_file)}")

                    # Podsumowanie
                    if do_summarize:
                        full_text = " ".join([s.text for s in segments])
                        summary = processor.summarize_text(full_text.strip(), style=summary_style)
                        if summary:
                            summary_file = os.path.splitext(output_base)[0] + "_podsumowanie.txt"
                            with open(summary_file, "w", encoding="utf-8") as f: f.write(summary)
                            all_output_files.append(summary_file)
                            self.log(f"Podsumowanie gotowe: {os.path.basename(summary_file)}")
            
                # Sprzątanie (tylko YouTube)
                if is_youtube_mode and self.delete_video_var.get() and video_file:
                     try: os.remove(video_file)
                     except: pass
                     # Usuwamy z listy wynikowej jeśli skasowano
                     if video_file in all_output_files:
                         all_output_files.remove(video_file)

            if not self.stop_event.is_set():
                valid_outputs = [f for f in all_output_files if f and os.path.exists(f)]
                self.root.after(0, lambda: self.show_action_buttons(valid_outputs))
                self.root.after(0, lambda: messagebox.showinfo("Sukces", "Przetwarzanie zakończone!"))
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
