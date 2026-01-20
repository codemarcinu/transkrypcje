import streamlit as st
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional

# Dodanie ścieżki projektu do sys.path, aby widzieć moduły src
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.core.processor import ContentProcessor
from src.utils.logger import setup_logger
from src.utils.config import WHISPER_LANGUAGES, WHISPER_MODELS, DEFAULT_MODEL_SIZE, DATA_OUTPUT
from src.utils.helpers import check_ffmpeg

logger = setup_logger()

# Konfiguracja strony
st.set_page_config(
    page_title="AI Course & Content Generator",
    page_icon="🎓",
    layout="wide"
)

# --- Helper Classes for Callbacks ---

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

def main():
    st.title("🎓 AI Course & Content Generator")

    # --- SIDEBAR: KONFIGURACJA GŁÓWNA ---
    with st.sidebar:
        st.header("⚙️ Konfiguracja")
        
        # 1. Główne zadania (Eksponowane lub w zwiniętym dla porządku)
        with st.expander("🛠️ Zadania i Proces", expanded=True):
            do_transcribe = st.checkbox("Wykonaj transkrypcję", value=True, help="Używa Whisper do zamiany mowy na tekst")
            download_subs = st.checkbox("Pobierz napisy", value=True, help="Użyj napisów YouTube zamiast Whisper")
            do_summarize = st.checkbox("Generuj podsumowanie", value=True)
            do_content_gen_on_fly = st.checkbox("Generuj Podręcznik (Treść)", value=False)

        # 2. Parametry AI
        with st.expander("🤖 Modele i Parametry", expanded=False):
            st.markdown("**Whisper**")
            language = st.selectbox("Język audio:", options=list(WHISPER_LANGUAGES.keys()), index=list(WHISPER_LANGUAGES.keys()).index("Polski"))
            model_size = st.selectbox("Model AI Whisper:", options=WHISPER_MODELS, index=WHISPER_MODELS.index(DEFAULT_MODEL_SIZE))
            
            st.divider()
            
            st.markdown("**Analiza LLM**")
            model_name_llm = st.selectbox("Model LLM", ["bielik", "qwen2.5-coder:32b"], index=0)
            summary_style = st.selectbox("Styl podsumowania:", options=["Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)"])

        # 3. Ścieżki i Formaty
        with st.expander("📂 Ścieżki i Formaty", expanded=False):
            output_path = st.text_input("Folder zapisu:", value=os.path.abspath(DATA_OUTPUT))
            output_format = st.selectbox("Format transkrypcji:", options=["txt", "txt_no_timestamps", "srt", "vtt"])
            yt_quality = st.selectbox("Jakość YT:", ["best", "worst", "audio_only"])
            audio_bitrate = "128k"

        # 4. Status Systemu
        st.divider()
        st.subheader("🖥️ Status Systemu")
        ffmpeg_ok, _ = check_ffmpeg()
        if ffmpeg_ok:
            st.success("FFmpeg: Dostępny")
        else:
            st.error("FFmpeg: Brak!")
            st.warning("Pobieranie w wysokiej jakości może zawieść.")

    # --- GŁÓWNY WIDOK ---
    tab_yt, tab_local, tab_content, tab_logs = st.tabs(["📺 YouTube", "📂 Pliki Lokalne", "📝 Generowanie Treści", "📋 Logi"])

    # --- YouTube Tab ---
    with tab_yt:
        st.header("Pobieranie z YouTube")
        yt_url = st.text_input("Wklej link do YouTube (Wideo lub Playlista):", key="yt_url_input")
        start_yt = st.button("🚀 Uruchom Przetwarzanie", type="primary", disabled=not yt_url, key="btn_start_yt")

    # --- Local Files Tab ---
    with tab_local:
        st.header("Przetwarzanie Plików Lokalnych")
        uploaded_file = st.file_uploader("Wybierz plik wideo/audio:", type=["mp4", "mp3", "m4a", "wav", "mkv", "avi"])
        convert_to_mp3 = st.checkbox("Konwertuj na MP3 przed startem", value=True)
        start_local = st.button("🚀 Uruchom Przetwarzanie", type="primary", disabled=not uploaded_file, key="btn_start_local")

    # --- Content Generation Tab (Manual) ---
    with tab_content:
        st.header("Generowanie Treści z Istniejących Transkrypcji")
        
        # Lista dostępnych plików
        if os.path.exists(DATA_OUTPUT):
            txt_files = [f for f in os.listdir(DATA_OUTPUT) if f.endswith('.txt') and not f.endswith('_podsumowanie.txt')]
            txt_files.sort(key=lambda x: os.path.getmtime(os.path.join(DATA_OUTPUT, x)), reverse=True)
        else:
            txt_files = []
            
        selected_file_name = st.selectbox("Wybierz plik transkrypcji:", txt_files, key="select_file_content")
        
        # Auto-temat
        clean_topic_name = ""
        if selected_file_name:
            clean_topic_name = selected_file_name.replace("_transkrypcja.txt", "").replace(".txt", "").replace("_", " ").title()
        
        topic_input = st.text_input(
            "Temat / Tytuł opracowania AI:", 
            value=clean_topic_name,
            key=f"topic_{selected_file_name}", 
            help="AI użyje tego tematu jako kontekstu."
        )
        
        start_content_gen = st.button("✍️ Generuj Treść (Tylko AI)", type="primary", disabled=not selected_file_name, key="btn_start_content")

    # --- Processing Logic ---
    if start_yt or start_local or start_content_gen:
        st.divider()
        st.header("📊 Postęp Przetwarzania")
        
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        progress_tracker = StreamlitProgress(progress_bar, status_text)
        stop_event = threading.Event()
        
        def progress_callback_wrapper(percent, stage, file_size=None):
            progress_tracker.update(percent, stage, file_size)
            
        processor = ContentProcessor(logger, stop_event, progress_callback_wrapper)
        
        try:
            with st.status("🤖 Przetwarzanie...", expanded=True) as status:
                final_result_path = None
                
                # CASE 1: Manual Content Generation
                if start_content_gen:
                    input_full_path = os.path.join(DATA_OUTPUT, selected_file_name)
                    st.write(f"Inicjowanie agentów dla: `{selected_file_name}`...")
                    final_result_path = processor.run_content_generation(input_full_path, topic_input, model_name=model_name_llm)
                    
                # CASE 2 & 3: YT or Local (Full Pipeline)
                else:
                    target_file_path = None
                    subtitle_path = None
                    txt_file = None
                    
                    # 1. Acquire File
                    if start_yt:
                        st.write("Pobieranie z YouTube...")
                        downloaded_items = processor.download_video(yt_url, output_path, yt_quality, audio_bitrate.replace('k', ''))
                        if downloaded_items:
                            item = downloaded_items[0]
                            target_file_path = item.get('video') if isinstance(item, dict) else item
                            subtitle_path = item.get('subtitles') if isinstance(item, dict) else None
                    
                    elif start_local and uploaded_file:
                        st.write("Zapisywanie pliku lokalnego...")
                        target_file_path = os.path.join(output_path, uploaded_file.name)
                        with open(target_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        if convert_to_mp3:
                            st.write("Konwersja na MP3...")
                            mp3_path = os.path.join(output_path, os.path.splitext(uploaded_file.name)[0] + ".mp3")
                            target_file_path = processor.convert_to_mp3(target_file_path, mp3_path)

                    # 2. Transcribe
                    if target_file_path and os.path.exists(target_file_path):
                        if download_subs and subtitle_path and os.path.exists(subtitle_path):
                            st.write("Używanie napisów z YT...")
                            txt_file = processor.convert_subtitles_to_txt(subtitle_path)
                        elif do_transcribe:
                            st.write(f"Transkrypcja ({model_size})...")
                            lang_code = WHISPER_LANGUAGES[language]
                            segments_gen, info = processor.transcribe_video(target_file_path, lang_code, model_size)
                            output_base = os.path.join(output_path, os.path.basename(target_file_path))
                            txt_file = processor.save_transcription(segments_gen, info, output_base, output_format, lang_code)
                    
                    # 3. Post-Process
                    if txt_file and os.path.exists(txt_file):
                        final_result_path = txt_file # Default result is transcription
                        
                        if do_summarize:
                            st.write("Generowanie podsumowania...")
                            summary = processor.summarize_from_file(txt_file, style=summary_style)
                            if summary:
                                summary_path = os.path.splitext(txt_file)[0] + "_podsumowanie.txt"
                                with open(summary_path, "w", encoding='utf-8') as f: f.write(summary)
                                final_result_path = summary_path # Prefer summary as preview if generated
                        
                        if do_content_gen_on_fly:
                            st.write("Pisanie podręcznika...")
                            auto_topic = os.path.splitext(os.path.basename(target_file_path))[0].replace('_', ' ').title()
                            final_result_path = processor.run_content_generation(txt_file, auto_topic, model_name=model_name_llm)

                # Update status and save to session state
                if final_result_path:
                    st.session_state['last_generated_result'] = final_result_path
                    status.update(label="✅ Gotowe!", state="complete", expanded=False)
                    st.success(f"Zakończono! Wynik zapisany w: `{final_result_path}`")
                else:
                    status.update(label="⚠️ Zakończono bez wyniku", state="complete")

        except Exception as e:
            st.error(f"❌ Wystąpił błąd: {e}")
            logger.log(f"Error in UI: {e}")

    # --- SEKCJA PODGLĄDU (PERSISTENT) ---
    if 'last_generated_result' in st.session_state and os.path.exists(st.session_state['last_generated_result']):
        result_file = st.session_state['last_generated_result']
        st.divider()
        st.markdown(f"### 📄 Podgląd ostatniego wyniku: `{os.path.basename(result_file)}`")
        
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                content = f.read()
            with st.container(border=True):
                if result_file.endswith('.md'):
                    st.markdown(content)
                else:
                    st.text(content)
            st.download_button(
                label="💾 Pobierz wynik",
                data=content,
                file_name=os.path.basename(result_file),
                mime="text/markdown" if result_file.endswith('.md') else "text/plain"
            )
        except Exception as e:
            st.error(f"Nie można wczytać podglądu: {e}")

    # --- Logs Tab ---
    with tab_logs:
        if os.path.exists("app_debug.log"):
            with open("app_debug.log", "r", encoding="utf-8") as f:
                logs = f.readlines()[-100:]
            st.code("".join(logs), language="log")
        else:
            st.info("Brak pliku logów.")

if __name__ == "__main__":
    main()
