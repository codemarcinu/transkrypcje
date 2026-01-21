import streamlit as st
import os
import sys
import json
import glob
import threading
import shutil
from pathlib import Path
from typing import Optional

# Dodanie ścieżki projektu do sys.path, aby widzieć moduły src
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.core.processor import ContentProcessor
from src.agents.writer import ReportWriter
from src.utils.prompts_config import PROMPT_TEMPLATES
from src.utils.logger import setup_logger
from src.utils.config import (
    WHISPER_LANGUAGES, WHISPER_MODELS, DEFAULT_MODEL_SIZE, 
    DATA_PROCESSED, DATA_OUTPUT
)
from src.utils.helpers import check_ffmpeg

logger = setup_logger()

# Konfiguracja strony
st.set_page_config(
    page_title="AI Note Generator v2.0",
    page_icon="🎙️",
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
    st.title("🎙️ AI Transkrypcja & Notatki v2.0")

    # Inicjalizacja Session State
    if 'selected_file_for_generation' not in st.session_state:
        st.session_state['selected_file_for_generation'] = None
    if 'last_generated_result' not in st.session_state:
        st.session_state['last_generated_result'] = None

    # --- SIDEBAR: KONFIGURACJA GŁÓWNA ---
    with st.sidebar:
        st.header("⚙️ Konfiguracja")
        
        # 1. Model Whisper
        st.subheader("🎙️ Model Whisper")
        language = st.selectbox("Język audio:", options=list(WHISPER_LANGUAGES.keys()), index=list(WHISPER_LANGUAGES.keys()).index("Polski"))
        model_size = st.selectbox("Wielkość modelu:", options=WHISPER_MODELS, index=WHISPER_MODELS.index(DEFAULT_MODEL_SIZE))

        st.divider()

        # 2. Główne zadania (Dla Tab 1)
        with st.expander("🛠️ Zadania i Proces", expanded=True):
            do_transcribe = st.checkbox("Wykonaj transkrypcję", value=True)
            download_subs = st.checkbox("Pobierz napisy (jeśli są)", value=True)
            do_summarize = st.checkbox("Generuj podsumowanie", value=True)
        
        # 3. Parametry LLM
        with st.expander("🧠 Ustawienia LLM", expanded=False):
            model_name_llm = st.selectbox("Model LLM", ["bielik", "qwen2.5-coder:32b"], index=0)
            summary_style = st.selectbox("Styl podsumowania:", options=["Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)"])

        # 4. Ścieżki
        with st.expander("📂 Ścieżki i Pliki", expanded=False):
            output_path = st.text_input("Folder zapisu:", value=os.path.abspath(DATA_OUTPUT))
            obsidian_vault = st.text_input("Vault Obsidian (opcjonalnie):", value="")
            output_format = st.selectbox("Format transkrypcji:", options=["txt", "txt_no_timestamps", "srt", "vtt"])
            yt_quality = st.selectbox("Jakość YT:", ["best", "worst", "audio_only"])
            audio_bitrate = "128k"

        st.divider()
        if st.button("🧹 Zwolnij VRAM (Force)", use_container_width=True):
            from src.core.llm_engine import unload_model
            from src.utils.config import MODEL_EXTRACTOR, MODEL_WRITER
            unload_model(MODEL_EXTRACTOR)
            unload_model(MODEL_WRITER)
            st.toast("Pamięć VRAM została wyczyszczona!", icon="🧹")

        st.divider()
        ffmpeg_ok, _ = check_ffmpeg()
        if ffmpeg_ok: st.success("FFmpeg: OK")
        else: st.error("FFmpeg: BRAK")

    # Dzielimy aplikację na dwie główne zakładki
    tab_main, tab_lab, tab_logs = st.tabs(["📂 Przetwarzanie Audio", "✍️ Laboratorium Tekstu (Writer)", "📋 Logi"])

    # --- TAB 1: Przetwarzanie Audio ---
    with tab_main:
        st.header("Nowa Transkrypcja")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.subheader("📺 YouTube")
            yt_url = st.text_input("Wklej link do YouTube:", key="yt_url_input")
            start_yt = st.button("🚀 Start YouTube", type="primary", disabled=not yt_url)
            
        with col_t2:
            st.subheader("📂 Plik Lokalny")
            uploaded_file = st.file_uploader("Wybierz plik:", type=["mp4", "mp3", "m4a", "wav", "mkv", "avi"])
            convert_to_mp3 = st.checkbox("Konwertuj na MP3", value=True)
            start_local = st.button("🚀 Start Plik Lokalny", type="primary", disabled=not uploaded_file)

        # Logika przetwarzania dla Tab 1
        if start_yt or start_local:
            st.divider()
            progress_bar = st.progress(0.0)
            status_text = st.empty()
            progress_tracker = StreamlitProgress(progress_bar, status_text)
            stop_event = threading.Event()
            
            processor = ContentProcessor(logger, stop_event, progress_tracker.update)
            
            try:
                with st.status("🤖 Przetwarzanie...", expanded=True) as status:
                    target_file_path = None
                    subtitle_path = None
                    txt_file = None
                    
                    if start_yt:
                        downloaded_items = processor.download_video(yt_url, output_path, yt_quality, audio_bitrate.replace('k', ''))
                        if downloaded_items:
                            item = downloaded_items[0]
                            target_file_path = item.get('video') if isinstance(item, dict) else item
                            subtitle_path = item.get('subtitles') if isinstance(item, dict) else None
                    else:
                        target_file_path = os.path.join(output_path, uploaded_file.name)
                        with open(target_file_path, "wb") as f: f.write(uploaded_file.getbuffer())
                        if convert_to_mp3:
                            mp3_path = os.path.join(output_path, os.path.splitext(uploaded_file.name)[0] + ".mp3")
                            target_file_path = processor.convert_to_mp3(target_file_path, mp3_path)

                    if target_file_path and os.path.exists(target_file_path):
                        if download_subs and subtitle_path and os.path.exists(subtitle_path):
                            txt_file = processor.convert_subtitles_to_txt(subtitle_path)
                        elif do_transcribe:
                            lang_code = WHISPER_LANGUAGES[language]
                            segments_gen, info = processor.transcribe_video(target_file_path, lang_code, model_size)
                            output_base = os.path.join(output_path, os.path.basename(target_file_path))
                            txt_file = processor.save_transcription(segments_gen, info, output_base, output_format, lang_code)
                    
                    if txt_file and os.path.exists(txt_file):
                        if do_summarize:
                            summary = processor.summarize_from_file(txt_file, style=summary_style)
                            if summary:
                                summary_path = os.path.splitext(txt_file)[0] + "_podsumowanie.txt"
                                with open(summary_path, "w", encoding='utf-8') as f: f.write(summary)
                        
                        st.session_state['last_generated_result'] = txt_file
                        status.update(label="✅ Gotowe!", state="complete", expanded=False)
                        st.success(f"Zakończono! Wynik: `{txt_file}`")
            except Exception as e:
                st.error(f"❌ Błąd: {e}")

    # --- TAB 2: NOWA FUNKCJONALNOŚĆ (Laboratorium Tekstu) ---
    with tab_lab:
        st.header("Generator i Edytor Notatek")
        
        # 1. Wybór pliku wiedzy (JSON)
        json_files = glob.glob(os.path.join(DATA_PROCESSED, "*.json"))
        # Sortowanie od najnowszych
        json_files.sort(key=os.path.getmtime, reverse=True)
        
        selected_file = st.selectbox(
            "Wybierz Bazę Wiedzy (plik JSON z ekstrakcji):", 
            json_files,
            format_func=lambda x: os.path.basename(x)
        )

        if selected_file:
            # Ładowanie danych
            with open(selected_file, 'r', encoding='utf-8') as f:
                knowledge_data = json.load(f)
            
            st.success(f"Wczytano {len(knowledge_data)} segmentów wiedzy.")
            
            # Kolumny dla ustawień Writera
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("⚙️ Konfiguracja")
                # Wybór trybu z pliku config
                mode_options = list(PROMPT_TEMPLATES.keys())
                selected_mode = st.selectbox("Styl Notatki", mode_options, index=0)
                
                # Pobranie domyślnych promptów dla wybranego trybu
                default_sys = PROMPT_TEMPLATES[selected_mode]["system"]
                default_user = PROMPT_TEMPLATES[selected_mode]["user"]
                
                st.markdown("---")
                # Domyślny temat z nazwy pliku
                auto_topic = os.path.basename(selected_file).replace(".json", "").replace("_transkrypcja.txt", "").replace(".txt", "").replace("_kb", "").replace("_", " ").title()
                topic_name = st.text_input("Temat notatki", value=auto_topic)
                
            with col2:
                st.subheader("🧠 Edycja Promptów (Advanced)")
                # Edytowalne pola tekstowe
                edited_system = st.text_area("System Prompt (Instrukcja Roli)", value=default_sys, height=200)
                edited_user = st.text_area("User Prompt (Szablon Zadania)", value=default_user, height=150)
                
                st.caption("Dostępne zmienne w User Prompt: `{topic_name}`, `{context_items}`")

            # Przycisk Generowania
            if st.button("🚀 Generuj Notatkę (Bielik Writer)", type="primary"):
                writer = ReportWriter()
                
                with st.spinner("Bielik pisze... To potrwa około 30-60 sekund..."):
                    final_md = writer.generate_chapter(
                        topic_name=topic_name,
                        aggregated_data=knowledge_data,
                        mode=selected_mode,
                        custom_system_prompt=edited_system,
                        custom_user_prompt=edited_user
                    )
                
                st.session_state['last_generated_result'] = final_md # Zapisujemy treść lub ścieżkę? User chce podgląd.
                
                st.subheader("📝 Wynik")
                st.markdown(final_md)
                
                # Zapis do pliku
                output_filename = os.path.basename(selected_file).replace(".json", f"_{selected_mode}.md")
                save_path = os.path.join(DATA_OUTPUT, output_filename)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(final_md)
                
                st.download_button("Pobierz .md", final_md, file_name=output_filename)
                st.success(f"Zapisano w: {save_path}")

                # Obsidian Export
                if obsidian_vault:
                    try:
                        shutil.copy(save_path, Path(obsidian_vault) / output_filename)
                        st.success(f"Skopiowano do Obsidian Vault.")
                    except: pass

    # --- TAB 3: Logi ---
    with tab_logs:
        st.markdown("### 📋 Logi Systemowe")
        if os.path.exists("app_debug.log"):
            with open("app_debug.log", "r", encoding="utf-8") as f:
                logs = f.readlines()[-50:]
            log_content = "".join(logs)
            st.markdown(f"""
            <div style="background-color: #0e1117; color: #00ff00; padding: 10px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; height: 400px; overflow-y: scroll;">
            {log_content}
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
