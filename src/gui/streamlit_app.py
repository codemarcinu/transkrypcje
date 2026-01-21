import streamlit as st
import os
import sys
import time
import threading
import shutil
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

    # Inicjalizacja Session State
    if 'selected_file_for_generation' not in st.session_state:
        st.session_state['selected_file_for_generation'] = None
    if 'auto_switch_tab' not in st.session_state:
        st.session_state['auto_switch_tab'] = False # Placeholder if we find a way to switch tabs

    # --- SIDEBAR: KONFIGURACJA GŁÓWNA ---
    with st.sidebar:
        st.header("⚙️ Konfiguracja")
        
        # 1. Model Whisper (Krytyczne - wyciągnięte na wierzch)
        st.subheader("🎙️ Model Whisper")
        language = st.selectbox("Język audio:", options=list(WHISPER_LANGUAGES.keys()), index=list(WHISPER_LANGUAGES.keys()).index("Polski"))
        model_size = st.selectbox("Wielkość modelu:", options=WHISPER_MODELS, index=WHISPER_MODELS.index(DEFAULT_MODEL_SIZE), help="Większy model = lepsza jakość, ale wolniej.")

        st.divider()

        # 2. Główne zadania
        with st.expander("🛠️ Zadania i Proces", expanded=True):
            do_transcribe = st.checkbox("Wykonaj transkrypcję", value=True)
            download_subs = st.checkbox("Pobierz napisy (jeśli są)", value=True)
            do_summarize = st.checkbox("Generuj podsumowanie", value=True)
            do_content_gen_on_fly = st.checkbox("Generuj Podręcznik (Automatycznie)", value=False, help="Jeśli zaznaczone, tworzy podręcznik od razu po transkrypcji.")

        # 3. Parametry LLM
        with st.expander("🧠 Ustawienia LLM", expanded=False):
            model_name_llm = st.selectbox("Model LLM", ["bielik", "qwen2.5-coder:32b"], index=0)
            summary_style = st.selectbox("Styl podsumowania:", options=["Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)"])

        # 4. Ścieżki
        with st.expander("📂 Ścieżki i Pliki", expanded=False):
            output_path = st.text_input("Folder zapisu:", value=os.path.abspath(DATA_OUTPUT))
            obsidian_vault = st.text_input("Vault Obsidian (opcjonalnie):", value="", help="Ścieżka do Twojego folderu Obsidian PKM.")
            output_format = st.selectbox("Format transkrypcji:", options=["txt", "txt_no_timestamps", "srt", "vtt"])
            yt_quality = st.selectbox("Jakość YT:", ["best", "worst", "audio_only"])
            audio_bitrate = "128k"

        # 5. Narzędzia Systemowe
        with st.sidebar:
            st.divider()
            if st.button("🧹 Zwolnij VRAM (Force)", use_container_width=True):
                from src.core.llm_engine import unload_model
                from src.utils.config import MODEL_EXTRACTOR, MODEL_WRITER
                unload_model(MODEL_EXTRACTOR)
                unload_model(MODEL_WRITER)
                st.toast("Pamięć VRAM została wyczyszczona!", icon="🧹")

        # 6. Status
        st.divider()
        st.caption("🖥️ Status Systemu")
        ffmpeg_ok, _ = check_ffmpeg()
        if ffmpeg_ok:
            st.success("FFmpeg: OK")
        else:
            st.error("FFmpeg: BRAK")

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
            st.warning(f"Katalog {DATA_OUTPUT} jest pusty lub nie istnieje!")
            txt_files = []
            
        # Determine index based on session state
        pre_idx = 0
        if st.session_state['selected_file_for_generation'] in txt_files:
            pre_idx = txt_files.index(st.session_state['selected_file_for_generation'])

        selected_file_name = st.selectbox(
            "Wybierz plik transkrypcji:", 
            txt_files, 
            index=pre_idx,
            key="select_file_content"
        )
        
        # Auto-temat (Dynamic)
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
                    
                    # Button to quick start generation
                    if final_result_path and final_result_path.endswith('.txt'):
                        cols = st.columns([1, 2])
                        with cols[0]:
                            if st.button("➡️ Generuj Podręcznik z tego pliku"):
                                st.session_state['selected_file_for_generation'] = os.path.basename(final_result_path)
                                st.info("Plik wybrany! Przejdź do zakładki 'Generowanie Treści'.")
                else:
                    status.update(label="⚠️ Zakończono bez wyniku", state="complete")

            st.error(f"❌ Wystąpił błąd: {e}")
            logger.log(f"Error in UI: {e}")
        
        # Statystyki po zakończeniu (jeśli to był kurs)
        if start_content_gen and 'final_result_path' in locals() and final_result_path:
            # Próbujemy odczytać statystyki z backupu lub logów (uproszczone wyświetlanie metryk)
            st.info("Podręcznik został wygenerowany z użyciem [[Wikilinks]] i YAML Frontmatter.")

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
            
            # Obsidian Export Button
            if result_file.endswith('.md') and obsidian_vault:
                if st.button("🚀 Wyślij do Obsidian Vault", type="primary"):
                    try:
                        vault_path = Path(obsidian_vault)
                        if vault_path.exists():
                            target = vault_path / os.path.basename(result_file)
                            shutil.copy(result_file, target)
                            st.success(f"Skopiowano do Obsidian: `{target}`")
                        else:
                            st.error(f"Ścieżka Vaulta nie istnieje: `{obsidian_vault}`")
                    except Exception as e:
                        st.error(f"Błąd eksportu: {e}")
        except Exception as e:
            st.error(f"Nie można wczytać podglądu: {e}")

    # --- Logs Tab ---
    with tab_logs:
        st.markdown("### 📋 Logi Systemowe")
        if os.path.exists("app_debug.log"):
            with open("app_debug.log", "r", encoding="utf-8") as f:
                logs = f.readlines()[-50:] # Show last 50 lines
            
            # Styl terminala
            log_content = "".join(logs)
            st.markdown(f"""
            <div style="background-color: #0e1117; color: #00ff00; padding: 10px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; height: 400px; overflow-y: scroll;">
            {log_content}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Brak pliku logów.")

if __name__ == "__main__":
    main()
