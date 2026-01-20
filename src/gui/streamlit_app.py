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
        
        self.stage_map = {
            "downloading": "📥 Pobieranie wideo...",
            "converting": "🔄 Przygotowywanie audio...",
            "transcribing": "👂 Przetwarzanie mowy (Whisper)...",
            "summarizing": "✍️ Generowanie podsumowania...",
            "content_generation": "🧠 Bielik pisze rozdział podręcznika...",
            "cleaning": "🧹 Porządkowanie plików..."
        }
        
    def update(self, percent: float, stage: str, file_size: Optional[str] = None):
        val = min(max(percent / 100.0, 0.0), 1.0)
        self.progress_bar.progress(val)
        
        friendly_stage = self.stage_map.get(stage.lower(), f"Pracuję: {stage}")
        msg = f"Status: {friendly_stage}"
        if file_size:
            msg += f" | Rozmiar: {file_size}"
        self.status_text.text(msg)

# --- Main App ---

def main():
    st.title("🎓 AI Course Generator & Transcriber")
    
    # --- Sidebar Config ---
    with st.sidebar:
        st.header("⚙️ Konfiguracja")
        
        # Advanced Expander
        with st.expander("🛠️ Ustawienia Zaawansowane", expanded=False):
            st.subheader("Główne zadania")
            do_transcribe = st.checkbox("Wykonaj transkrypcję", value=True, help="Używa Whisper do zamiany mowy na tekst")
            download_subs = st.checkbox("Pobierz napisy", value=True, help="Jeśli YouTube posiada napisy, użyjemy ich zamiast Whisper (szybciej!)")
            do_summarize = st.checkbox("Generuj podsumowanie", value=True)
            do_content_gen = st.checkbox("Generuj Podręcznik (Treść)", value=False)
            
            st.divider()
            
            output_path = st.text_input("Folder zapisu:", value=os.path.abspath(DATA_OUTPUT))
            
            st.divider()
            
            # Whisper Settings
            st.markdown("**Parametry Whisper**")
            language = st.selectbox("Język audio:", options=list(WHISPER_LANGUAGES.keys()), index=list(WHISPER_LANGUAGES.keys()).index("Polski"))
            model_size = st.selectbox("Model AI:", options=WHISPER_MODELS, index=WHISPER_MODELS.index(DEFAULT_MODEL_SIZE))
            output_format = st.selectbox("Format pliku:", options=["txt", "txt_no_timestamps", "srt", "vtt"])
            
            st.divider()
            
            # AI Processing Settings
            st.markdown("**Parametry Analizy**")
            summary_style = st.selectbox("Styl podsumowania:", options=["Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)"])
        
        st.info("💡 Skonfiguruj zadania w 'Ustawieniach Zaawansowanych', jeśli chcesz zmienić domyślne parametry.")

    # Static settings from audit
    yt_audio_quality = "128" # Fixed for Whisper
            
    # --- Main Content ---
    
    tab_yt, tab_local, tab_content = st.tabs(["📺 YouTube", "📂 Pliki Lokalne", "📝 Generowanie Treści"])
    
    # Initialize Session State for Logs
    if "logs" not in st.session_state:
        st.session_state.logs = []

    # --- YouTube Tab ---
    with tab_yt:
        st.header("Pobieranie z YouTube")
        yt_url = st.text_input("Wklej link do YouTube (Wideo lub Playlista):")
        
        with st.expander("Opcje pobierania"):
            yt_quality = st.selectbox("Jakość wideo:", ["best", "worst", "audio_only"])
            # yt_audio_quality is now simplified and hidden (set to 128k in logic)
            
        start_yt = st.button("🚀 Uruchom Przetwarzanie", type="primary", disabled=not yt_url, key="btn_start_yt")

    # --- Local Files Tab ---
    with tab_local:
        st.header("Przetwarzanie Plików Lokalnych")
        uploaded_file = st.file_uploader("Wybierz plik wideo/audio:", type=["mp4", "mp3", "m4a", "wav", "mkv", "avi"])
        convert_to_mp3 = st.checkbox("Konwertuj na MP3 przed startem (zalecane dla m4a)", value=True)
        
        start_local = st.button("🚀 Uruchom Przetwarzanie", type="primary", disabled=not uploaded_file, key="btn_start_local")

    # --- Content Generation Tab ---
    with tab_content:
        st.header("Generowanie Treści z Transkrypcji")
        
        # Refresh file list
        if os.path.exists(DATA_OUTPUT):
            txt_files = [f for f in os.listdir(DATA_OUTPUT) if f.endswith('.txt') and not f.endswith('_podsumowanie.txt')]
            txt_files.sort(key=lambda x: os.path.getmtime(os.path.join(DATA_OUTPUT, x)), reverse=True)
        else:
            txt_files = []
            
        selected_file_name = st.selectbox("Wybierz plik transkrypcji:", txt_files)
        
        # Enhanced Auto-suggestion
        default_topic = ""
        if selected_file_name:
             clean_name = selected_file_name.replace('_transkrypcja.txt', '').replace('.txt', '').replace('_', ' ').title()
             default_topic = clean_name
             
        topic_input = st.text_input("✨ Temat / Tytuł opracowania AI:", value=default_topic, key=f"topic_{selected_file_name}")
        
        start_content_gen = st.button("✍️ Generuj Treść (Tylko AI)", type="primary", disabled=not selected_file_name)

    # --- Processing Logic ---
    
    # Common Setup
    if start_yt or start_local or start_content_gen:
        st.divider()
        st.header("📊 Postęp Przetwarzania")
        
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        logger = StreamlitLogger()
        progress_tracker = StreamlitProgress(progress_bar, status_text)
        stop_event = threading.Event()
        
        def progress_callback_wrapper(percent, stage, file_size=None):
            progress_tracker.update(percent, stage, file_size)
            
        processor = Processor(logger, stop_event, progress_callback_wrapper)
        
        try:
            with st.spinner("Pracuję..."):
                final_md_path = None
                
                # CASE 1: Content Generation Only
                if start_content_gen and selected_file_name:
                    input_full_path = os.path.join(DATA_OUTPUT, selected_file_name)
                    final_md_path = os.path.splitext(input_full_path)[0] + "_content.md" # Better naming
                    
                    logger.log(f"Rozpoczynam generowanie treści dla: {selected_file_name}")
                    processor.run_content_generation(input_full_path, final_md_path, topic=topic_input)
                    st.session_state['last_generated_file'] = final_md_path
                    st.success("✅ Generowanie treści zakończone!")

                # CASE 2: Full Pipeline (YT or Local)
                else:
                    target_file_path = None
                    subtitle_path = None
                    txt_file = None
                    
                    # 1. Acquire File
                    if start_yt:
                        logger.log(f"Pobieranie z URL: {yt_url}")
                        downloaded_items = processor.download_video(yt_url, output_path, yt_quality, yt_audio_quality)
                        
                        if downloaded_items:
                            item = downloaded_items[0]
                            if isinstance(item, dict):
                                target_file_path = item.get('video')
                                subtitle_path = item.get('subtitles')
                            else:
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
                        if download_subs and subtitle_path and os.path.exists(subtitle_path):
                            logger.log("Znaleziono napisy. Konwertowanie...")
                            txt_file = processor.convert_subtitles_to_txt(subtitle_path)
                            logger.log(f"Użyto napisów. Plik: {txt_file}")
                        elif do_transcribe:
                            logger.log(f"Rozpoczynam transkrypcję: {target_file_path}")
                            lang_code = WHISPER_LANGUAGES[language]
                            segments_gen, info = processor.transcribe_video(target_file_path, lang_code, model_size)
                            output_base = os.path.join(output_path, os.path.basename(target_file_path))
                            txt_file = processor.save_transcription(segments_gen, info, output_base, output_format, lang_code)
                            logger.log(f"Zapisano transkrypcję: {txt_file}")
                        
                        # 3. Post-Processing
                        if txt_file and os.path.exists(txt_file):
                            if do_summarize:
                                logger.log("Generowanie podsumowania...")
                                summary = processor.summarize_from_file(txt_file, style=summary_style)
                                if summary:
                                    summary_path = os.path.splitext(txt_file)[0] + "_podsumowanie.txt"
                                    with open(summary_path, "w", encoding='utf-8') as f:
                                        f.write(summary)
                                    logger.log(f"Zapisano posumowanie: {summary_path}")
                            
                            if do_content_gen:
                                logger.log("Uruchamianie generatora treści...")
                                final_md_path = os.path.splitext(txt_file)[0] + "_podrecznik.md"
                                auto_topic = os.path.splitext(os.path.basename(target_file_path))[0].replace('_', ' ').capitalize()
                                processor.run_content_generation(txt_file, final_md_path, topic=auto_topic)
                                logger.log(f"Treść wygenerowana.")
                    
                # --- Markdown Preview Logic ---
                if final_md_path and os.path.exists(final_md_path):
                    st.session_state['last_generated_file'] = final_md_path
            
            st.success("✅ Zakończono pomyślnie!")

        except Exception as e:
            st.error(f"❌ Wystąpił błąd: {e}")
            logger.log(f"ERROR: {e}")

    # --- Markdown Preview Persistent Display ---
    if 'last_generated_file' in st.session_state:
        final_md_path = st.session_state['last_generated_file']
        if os.path.exists(final_md_path):
            st.divider()
            st.markdown("### 📄 Podgląd wygenerowanej treści:")
            with open(final_md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            st.markdown(md_content)
            st.download_button("💾 Pobierz plik Markdown", md_content, file_name=os.path.basename(final_md_path))

    # --- Logs Display ---
    st.divider()
    with st.expander("📋 Logi Systemowe"):
        if st.session_state.logs:
            st.code("\n".join(st.session_state.logs), language="text")
        else:
            st.info("Brak logów. Przetwarzanie jeszcze się nie rozpoczęło.")

if __name__ == "__main__":
    main()
