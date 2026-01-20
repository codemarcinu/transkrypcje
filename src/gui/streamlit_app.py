import streamlit as st
import os
import time
import threading
from typing import Optional

from src.core.processor import Processor
from src.utils.config import WHISPER_LANGUAGES, WHISPER_MODELS, DEFAULT_MODEL_SIZE, DATA_OUTPUT

st.set_page_config(page_title="AI Course Generator", layout="wide")

# --- Helper Classes for Callbacks ---

class StreamlitLogger:
    def __init__(self):
        if "logs" not in st.session_state:
            st.session_state.logs = []
            
    def log(self, message: str):
        timestamp = time.strftime('%H:%M:%S')
        entry = f"[{timestamp}] {message}"
        st.session_state.logs.append(entry)
        print(entry) # Backup to console

class StreamlitProgress:
    def __init__(self, progress_bar, status_text):
        self.progress_bar = progress_bar
        self.status_text = status_text
        
    def update(self, percent: float, stage: str, file_size: Optional[str] = None):
        val = min(max(percent / 100.0, 0.0), 1.0)
        self.progress_bar.progress(val)
        
        msg = f"Status: {stage}"
        if file_size:
            msg += f" | Rozmiar: {file_size}"
        self.status_text.text(msg)

# --- Main App ---

def main():
    st.title("🎓 AI Course Generator & Transcriber")
    
    # --- Sidebar Config ---
    with st.sidebar:
        st.header("Konfiguracja")
        
        # Paths
        output_path = st.text_input("Folder zapisu:", value=os.path.abspath(DATA_OUTPUT))
        
        st.divider()
        
        # Whisper Settings
        st.subheader("Whisper (Transkrypcja)")
        do_transcribe = st.checkbox("Wykonaj transkrypcję", value=True)
        # New Checkbox
        download_subs = st.checkbox("Pobierz napisy (jeśli dostępne)", value=True)
        
        language = st.selectbox("Język audio:", options=list(WHISPER_LANGUAGES.keys()), index=list(WHISPER_LANGUAGES.keys()).index("Polski"))
        model_size = st.selectbox("Model Whisper:", options=WHISPER_MODELS, index=WHISPER_MODELS.index(DEFAULT_MODEL_SIZE))
        output_format = st.selectbox("Format wyjściowy:", options=["txt", "txt_no_timestamps", "srt", "vtt"])
        
        st.divider()
        
        # AI Processing Settings
        st.subheader("Ollama (Analiza)")
        do_summarize = st.checkbox("Generuj podsumowanie", value=True)
        do_content_gen = st.checkbox("Generuj Podręcznik (Treść)", value=False)
        summary_style = st.selectbox("Styl podsumowania:", options=["Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)"])

    # --- Main Content ---
    
    tab_yt, tab_local, tab_content = st.tabs(["YouTube", "Pliki Lokalne", "Generowanie Treści"])
    
    # Initialize Session State for Logs
    if "logs" not in st.session_state:
        st.session_state.logs = []

    # --- YouTube Tab ---
    with tab_yt:
        st.header("Pobieranie z YouTube")
        yt_url = st.text_input("Wklej link do YouTube:")
        
        col1, col2 = st.columns(2)
        with col1:
            yt_quality = st.selectbox("Jakość wideo:", ["best", "worst", "audio_only"])
        with col2:
            yt_audio_quality = st.selectbox("Jakość audio (kbps):", ["128", "192", "256", "320"], index=3)
            
        start_yt = st.button("Uruchom przetwarzanie (YouTube)", type="primary", disabled=not yt_url)

    # --- Local Files Tab ---
    with tab_local:
        st.header("Przetwarzanie Plików Lokalnych")
        uploaded_file = st.file_uploader("Wybierz plik wideo/audio:", type=["mp4", "mp3", "m4a", "wav", "mkv", "avi"])
        convert_to_mp3 = st.checkbox("Konwertuj na MP3 przed startem (zalecane dla m4a)", value=True)
        
        start_local = st.button("Uruchom przetwarzanie (Lokalne)", type="primary", disabled=not uploaded_file)

    # --- Content Generation Tab ---
    with tab_content:
        st.header("Generowanie Treści z Istniejącej Transkrypcji")
        
        # Refresh file list
        if os.path.exists(DATA_OUTPUT):
            txt_files = [f for f in os.listdir(DATA_OUTPUT) if f.endswith('.txt') and not f.endswith('_podsumowanie.txt')]
            # Sort by modification time (newest first)
            txt_files.sort(key=lambda x: os.path.getmtime(os.path.join(DATA_OUTPUT, x)), reverse=True)
        else:
            txt_files = []
            
        selected_file_name = st.selectbox("Wybierz plik transkrypcji:", txt_files)
        
        # Topic input default
        default_topic = ""
        if selected_file_name:
             # Remove _transkrypcja suffix if present for cleaner title
             clean_name = selected_file_name.replace('_transkrypcja.txt', '').replace('.txt', '')
             default_topic = clean_name.replace('_', ' ').capitalize()
             
        topic_input = st.text_input("Temat / Tytuł rozdziału:", value=default_topic)
        
        start_content_gen = st.button("Generuj Treść (Tylko AI)", type="primary", disabled=not selected_file_name)

    # --- Processing Logic ---
    
    # Common Setup
    if start_yt or start_local or start_content_gen:
        st.divider()
        st.header("Postęp Przetwarzania")
        
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        logger = StreamlitLogger()
        progress_tracker = StreamlitProgress(progress_bar, status_text)
        stop_event = threading.Event()
        
        def progress_callback_wrapper(percent, stage, file_size=None):
            progress_tracker.update(percent, stage, file_size)
            
        processor = Processor(logger, stop_event, progress_callback_wrapper)
        
        try:
            with st.spinner("Przetwarzanie w toku..."):
                # CASE 1: Content Generation Only
                if start_content_gen and selected_file_name:
                    input_full_path = os.path.join(DATA_OUTPUT, selected_file_name)
                    output_file_dummy = os.path.join(DATA_OUTPUT, "dummy_for_dir_extraction") 
                    
                    logger.log(f"Rozpoczynam generowanie treści dla: {selected_file_name}")
                    processor.run_content_generation(input_full_path, output_file_dummy, topic=topic_input)
                    st.success("Generowanie treści zakończone!")
                    return # Stop here for this flow

                # CASE 2: Full Pipeline (YT or Local)
                target_file_path = None
                subtitle_path = None
                txt_file = None
                
                # 1. Acquire File
                if start_yt:
                    logger.log(f"Pobieranie z URL: {yt_url}")
                    # Returns list of dicts now: [{'video': path, 'subtitles': path_or_None}]
                    downloaded_items = processor.download_video(yt_url, output_path, yt_quality, yt_audio_quality)
                    
                    if downloaded_items:
                        item = downloaded_items[0] # Assume single video for now
                        if isinstance(item, dict):
                            target_file_path = item.get('video')
                            subtitle_path = item.get('subtitles')
                        else:
                            # Fallback if old downloader version somehow used (unlikely)
                            target_file_path = item
                            
                        logger.log(f"Pobrano plik: {target_file_path}")
                        if subtitle_path:
                            logger.log(f"Pobrano napisy: {subtitle_path}")
                        
                elif start_local and uploaded_file:
                    logger.log(f"Zapisywanie przesłanego pliku: {uploaded_file.name}")
                    target_file_path = os.path.join(output_path, uploaded_file.name)
                    with open(target_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    if convert_to_mp3:
                        logger.log("Konwersja do MP3...")
                        mp3_path = os.path.join(output_path, os.path.splitext(uploaded_file.name)[0] + ".mp3")
                        target_file_path = processor.convert_to_mp3(target_file_path, mp3_path)

                # 2. Process File (Convert Subs OR Transcribe)
                if target_file_path and os.path.exists(target_file_path):
                    
                    # Try to use subtitles if available and requested
                    if download_subs and subtitle_path and os.path.exists(subtitle_path):
                        logger.log("Znaleziono napisy. Konwertowanie do formatu transkrypcji...")
                        # Convert subs to txt
                        base_name = os.path.basename(target_file_path)
                        output_base = os.path.join(output_path, base_name)
                        # Reuse save_transcription logic naming convention or just manual
                        # Use processor helper
                        txt_file = processor.convert_subtitles_to_txt(subtitle_path)
                        logger.log(f"Użyto napisów zamiast Whisper. Plik: {txt_file}")
                        
                    elif do_transcribe:
                        logger.log(f"Rozpoczynam transkrypcję (Whisper): {target_file_path}")
                        lang_code = WHISPER_LANGUAGES[language]
                        segments_gen, info = processor.transcribe_video(target_file_path, lang_code, model_size)
                        
                        base_name = os.path.basename(target_file_path)
                        output_base = os.path.join(output_path, base_name)
                        txt_file = processor.save_transcription(segments_gen, info, output_base, output_format, lang_code)
                        logger.log(f"Zapisano transkrypcję: {txt_file}")
                    
                    # 3. Post-Processing (Summarize / Content Gen)
                    if txt_file and os.path.exists(txt_file):
                        # Summarize
                        if do_summarize:
                            logger.log("Generowanie podsumowania...")
                            summary = processor.summarize_from_file(txt_file, style=summary_style)
                            if summary:
                                summary_path = os.path.splitext(txt_file)[0] + "_podsumowanie.txt"
                                with open(summary_path, "w", encoding='utf-8') as f:
                                    f.write(summary)
                                logger.log(f"Zapisano posumowanie: {summary_path}")
                        
                        # Content Gen
                        if do_content_gen:
                            logger.log("Uruchamianie generatora treści...")
                            osint_file = os.path.splitext(txt_file)[0] + "_raport_osint.md"
                            # Default topic for auto-run
                            auto_topic = os.path.splitext(os.path.basename(target_file_path))[0].replace('_', ' ').capitalize()
                            processor.run_content_generation(txt_file, osint_file, topic=auto_topic)
                            logger.log(f"Treść wygenerowana.")
                            
            st.success("Zakończono pomyślnie!")
            
        except Exception as e:
            st.error(f"Wystąpił błąd: {e}")
            logger.log(f"ERROR: {e}")

    # --- Logs Display ---
    st.divider()
    with st.expander("Logi Systemowe", expanded=True):
        if st.session_state.logs:
            st.code("\n".join(st.session_state.logs), language="text")
        else:
            st.info("Brak logów. Przetwarzanie jeszcze się nie rozpoczęło.")

if __name__ == "__main__":
    main()
