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
from src.agents.extractor import KnowledgeExtractor
from src.utils.prompts_config import PROMPT_TEMPLATES
from src.utils.logger import setup_logger
from src.utils.config import (
    WHISPER_LANGUAGES, WHISPER_MODELS, DEFAULT_MODEL_SIZE,
    DATA_PROCESSED, DATA_OUTPUT, CHUNK_SIZE, OVERLAP, MODEL_EXTRACTOR
)
from src.utils.helpers import check_ffmpeg
from src.core.text_cleaner import clean_transcript
from src.utils.text_processing import smart_split_text
from src.core.llm_engine import unload_model

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


def _process_single_file(processor, target_file_path, subtitle_path, output_path,
                         download_subs, do_transcribe, do_summarize,
                         lang_code, model_size, output_format, summary_style):
    """Przetwarza pojedynczy plik audio/video i zwraca (txt_file, json_file)."""
    txt_file = None
    json_file = None

    if target_file_path and os.path.exists(target_file_path):
        if download_subs and subtitle_path and os.path.exists(subtitle_path):
            txt_file = processor.convert_subtitles_to_txt(subtitle_path)
        elif do_transcribe:
            segments_gen, info = processor.transcribe_video(target_file_path, lang_code, model_size)
            output_base = os.path.join(output_path, os.path.basename(target_file_path))
            txt_file, json_file = processor.save_transcription(segments_gen, info, output_base, output_format, lang_code)

        if txt_file and os.path.exists(txt_file) and do_summarize:
            summary = processor.summarize_from_file(txt_file, style=summary_style)
            if summary:
                summary_path = os.path.splitext(txt_file)[0] + "_podsumowanie.txt"
                with open(summary_path, "w", encoding='utf-8') as f:
                    f.write(summary)

    return txt_file, json_file


def _run_knowledge_extraction(txt_file: str, progress_bar, status_text) -> Optional[str]:
    """
    Uruchamia ekstrakcję wiedzy z pliku transkrypcji.
    Zwraca ścieżkę do pliku JSON lub None w przypadku błędu.
    """
    if not txt_file or not os.path.exists(txt_file):
        return None

    try:
        # 1. Wczytaj i wyczyść transkrypcję
        status_text.text("🔍 Przygotowywanie tekstu do analizy...")
        progress_bar.progress(0.05)

        with open(txt_file, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        clean_text = clean_transcript(raw_text)
        chunks = smart_split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)

        if not chunks:
            status_text.text("⚠️ Brak tekstu do analizy")
            return None

        status_text.text(f"📦 Podzielono na {len(chunks)} fragmentów. Rozpoczynam ekstrakcję...")
        progress_bar.progress(0.1)

        # 2. Ekstrakcja wiedzy
        knowledge_base = []
        extractor = KnowledgeExtractor()
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            progress_pct = int(((i + 1) / total_chunks) * 100)
            time_tag = f"Part {i+1} ({progress_pct}%)"

            status_text.text(f"🧠 Analizuję fragment {i+1}/{total_chunks}...")

            graph = extractor.extract_knowledge(chunk, chunk_id=time_tag)
            knowledge_base.append(graph.model_dump())

            # Update progress (10% start + 80% for extraction)
            extraction_progress = 0.1 + (0.8 * (i + 1) / total_chunks)
            progress_bar.progress(extraction_progress)

        # 3. Zapis JSON
        status_text.text("💾 Zapisywanie bazy wiedzy...")
        progress_bar.progress(0.95)

        # Nazwa pliku JSON bazuje na nazwie transkrypcji
        base_name = os.path.basename(txt_file).replace('.txt', '')
        json_filename = f"{base_name}_kb.json"
        json_path = os.path.join(DATA_PROCESSED, json_filename)

        os.makedirs(DATA_PROCESSED, exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

        # 4. Zwolnij VRAM po ekstrakcji
        unload_model(MODEL_EXTRACTOR)

        progress_bar.progress(1.0)
        status_text.text(f"✅ Ekstrakcja zakończona! Zapisano: {json_filename}")

        return json_path

    except Exception as e:
        status_text.text(f"❌ Błąd ekstrakcji: {e}")
        return None


def _extract_topic_from_filename(filename: str) -> str:
    """Wyciąga czytelny temat z nazwy pliku."""
    # Usuń rozszerzenia i suffiksy
    topic = os.path.basename(filename)
    for suffix in ['.json', '.txt', '.mp4', '.mp3', '_transkrypcja', '_kb', '_podsumowanie']:
        topic = topic.replace(suffix, '')

    # Zamień separatory na spacje
    topic = topic.replace('_', ' ').replace('-', ' ')

    # Usuń datę z początku (YYYY-MM-DD)
    import re
    topic = re.sub(r'^\d{4}\s*\d{2}\s*\d{2}\s*', '', topic)

    # Capitalize i przytnij
    return topic.strip().title()[:100]


def main():
    st.title("🎙️ AI Transkrypcja & Notatki v2.0")

    # Inicjalizacja Session State
    if 'selected_file_for_generation' not in st.session_state:
        st.session_state['selected_file_for_generation'] = None
    if 'last_generated_result' not in st.session_state:
        st.session_state['last_generated_result'] = None
    if 'last_extraction_json' not in st.session_state:
        st.session_state['last_extraction_json'] = None
    if 'last_topic_name' not in st.session_state:
        st.session_state['last_topic_name'] = None
    if 'go_to_lab' not in st.session_state:
        st.session_state['go_to_lab'] = False

    # --- SIDEBAR: KONFIGURACJA GŁÓWNA ---
    with st.sidebar:
        st.header("⚙️ Konfiguracja")
        
        # 1. Model Whisper
        st.subheader("🎙️ Model Whisper")
        language = st.selectbox(
            "Język audio:",
            options=list(WHISPER_LANGUAGES.keys()),
            index=list(WHISPER_LANGUAGES.keys()).index("Polski")
        )

        # Opisy modeli dla użytkownika
        model_descriptions = {
            "medium": "medium — szybszy (~5 GB VRAM)",
            "large-v3": "large-v3 — najlepsza jakość (~8 GB VRAM)"
        }
        model_size = st.selectbox(
            "Wielkość modelu:",
            options=WHISPER_MODELS,
            index=WHISPER_MODELS.index(DEFAULT_MODEL_SIZE),
            format_func=lambda x: model_descriptions.get(x, x),
            help="medium: dobry kompromis szybkość/jakość. large-v3: najlepsza dokładność dla polskiego."
        )

        st.divider()

        # 2. Główne zadania - najważniejsze opcje NA WIERZCHU
        st.subheader("🛠️ Co zrobić?")
        do_transcribe = st.checkbox("Transkrypcja (Whisper)", value=True)
        do_extraction = st.checkbox(
            "Ekstrakcja wiedzy (do Laboratorium)",
            value=True,
            help="Analizuje transkrypcję i wyciąga kluczowe pojęcia, narzędzia i wskazówki. Wymagane do generowania notatek w Laboratorium."
        )
        do_summarize = st.checkbox("Podsumowanie (LLM)", value=False)

        st.divider()

        # 3. Ustawienia wyjścia - często używane
        st.subheader("📂 Gdzie zapisać?")
        output_path = st.text_input("Folder zapisu:", value=os.path.abspath(DATA_OUTPUT))
        output_format = st.selectbox(
            "Format transkrypcji:",
            options=["json", "txt", "txt_no_timestamps", "srt", "vtt"],
            help="json: bazowy format (zalecany), txt: z timestampami, srt/vtt: napisy"
        )

        # 4. Opcje zaawansowane - ukryte
        with st.expander("⚙️ Opcje zaawansowane", expanded=False):
            download_subs = st.checkbox("Pobierz napisy YT (jeśli są)", value=True)
            summary_style = st.selectbox(
                "Styl podsumowania:",
                options=["Zwięzłe (3 punkty)", "Krótkie (1 akapit)", "Szczegółowe (Pełne)"]
            )
            yt_quality = st.selectbox("Jakość pobierania YT:", ["best", "audio_only", "worst"])
            audio_bitrate = "128k"
            obsidian_vault = st.text_input("Vault Obsidian:", value="", help="Opcjonalne - ścieżka do vault Obsidian")

            st.divider()
            if st.button("🧹 Zwolnij VRAM", use_container_width=True):
                from src.utils.config import MODEL_WRITER
                unload_model(MODEL_EXTRACTOR)
                unload_model(MODEL_WRITER)
                st.toast("Pamięć VRAM została wyczyszczona!", icon="🧹")

        # Status FFmpeg - na dole
        st.divider()
        ffmpeg_ok, _ = check_ffmpeg()
        if ffmpeg_ok:
            st.success("FFmpeg: OK", icon="✅")
        else:
            st.error("FFmpeg: BRAK - wymagany do konwersji audio!", icon="⚠️")

    # Dzielimy aplikację na dwie główne zakładki
    tab_main, tab_lab = st.tabs(["📂 Przetwarzanie Audio", "✍️ Laboratorium Tekstu"])

    # --- TAB 1: Przetwarzanie Audio ---
    with tab_main:
        st.header("Nowa Transkrypcja")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.subheader("📺 YouTube")
            yt_url = st.text_input(
                "Wklej link do YouTube:",
                key="yt_url_input",
                placeholder="https://www.youtube.com/watch?v=...",
                help="Wklej pełny link do filmu YouTube"
            )
            start_yt = st.button("🚀 Start YouTube", type="primary", disabled=not yt_url)
            
        with col_t2:
            st.subheader("📂 Plik Lokalny")
            uploaded_files = st.file_uploader(
                "Wybierz pliki (możesz przeciągnąć lub wybrać wiele):",
                type=["mp4", "mp3", "m4a", "wav", "mkv", "avi"],
                accept_multiple_files=True,
                help="Przeciągnij pliki lub kliknij aby wybrać. Obsługiwane: MP4, MP3, M4A, WAV, MKV, AVI"
            )

            # Pokaż listę wybranych plików
            if uploaded_files:
                st.caption(f"Wybrano {len(uploaded_files)} plik(ów): {', '.join([f.name for f in uploaded_files[:3]])}{'...' if len(uploaded_files) > 3 else ''}")

            # Sprawdź czy wszystkie pliki to już MP3
            all_mp3 = uploaded_files and all(f.name.lower().endswith('.mp3') for f in uploaded_files)
            if not all_mp3:
                convert_to_mp3 = st.checkbox("Konwertuj na MP3", value=True)
            else:
                convert_to_mp3 = False

            start_local = st.button("🚀 Start Plik Lokalny", type="primary", disabled=not uploaded_files)

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
                    results = []

                    if start_yt:
                        # YouTube - pojedynczy link
                        downloaded_items = processor.download_video(yt_url, output_path, yt_quality, audio_bitrate.replace('k', ''))
                        if downloaded_items:
                            item = downloaded_items[0]
                            target_file_path = item.get('video') if isinstance(item, dict) else item
                            subtitle_path = item.get('subtitles') if isinstance(item, dict) else None

                            txt_file, json_file = _process_single_file(
                                processor, target_file_path, subtitle_path, output_path,
                                download_subs, do_transcribe, do_summarize,
                                WHISPER_LANGUAGES[language], model_size, output_format, summary_style
                            )
                            if txt_file:
                                results.append(txt_file)
                            if json_file:
                                st.success(f"📦 Bazowy JSON: `{os.path.basename(json_file)}`")
                    else:
                        # Pliki lokalne - obsługa wielu
                        total_files = len(uploaded_files)
                        for idx, uploaded_file in enumerate(uploaded_files, 1):
                            st.write(f"📄 Przetwarzanie ({idx}/{total_files}): **{uploaded_file.name}**")

                            target_file_path = os.path.join(output_path, uploaded_file.name)
                            with open(target_file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())

                            if convert_to_mp3 and not uploaded_file.name.lower().endswith('.mp3'):
                                mp3_path = os.path.join(output_path, os.path.splitext(uploaded_file.name)[0] + ".mp3")
                                target_file_path = processor.convert_to_mp3(target_file_path, mp3_path)

                            txt_file, json_file = _process_single_file(
                                processor, target_file_path, None, output_path,
                                False, do_transcribe, do_summarize,
                                WHISPER_LANGUAGES[language], model_size, output_format, summary_style
                            )
                            if txt_file:
                                results.append(txt_file)
                            if json_file:
                                st.success(f"📦 Bazowy JSON: `{os.path.basename(json_file)}`")

                    if results:
                        st.session_state['last_generated_result'] = results[-1]

                        # === EKSTRAKCJA WIEDZY ===
                        extraction_results = []
                        if do_extraction and results:
                            st.write("---")
                            st.write("🧠 **Etap 2: Ekstrakcja wiedzy**")
                            extraction_progress = st.progress(0.0)
                            extraction_status = st.empty()

                            for txt_file in results:
                                extraction_status.text(f"Analizuję: {os.path.basename(txt_file)}...")
                                json_path = _run_knowledge_extraction(txt_file, extraction_progress, extraction_status)
                                if json_path:
                                    extraction_results.append(json_path)
                                    # Zapisz do session state
                                    st.session_state['last_extraction_json'] = json_path
                                    st.session_state['last_topic_name'] = _extract_topic_from_filename(txt_file)

                        # === PODSUMOWANIE ===
                        status.update(label=f"✅ Gotowe! Przetworzono {len(results)} plik(ów)", state="complete", expanded=False)

                        for r in results:
                            st.success(f"📝 Transkrypcja: `{os.path.basename(r)}`")

                        if extraction_results:
                            for e in extraction_results:
                                st.success(f"🧠 Baza wiedzy: `{os.path.basename(e)}`")

                            # Przycisk przejścia do Laboratorium
                            st.divider()
                            st.info("✨ **Gotowe do generowania notatek!** Kliknij poniżej, aby przejść do Laboratorium Tekstu.")

                            if st.button("🚀 Przejdź do Laboratorium Tekstu", type="primary", use_container_width=True):
                                st.session_state['go_to_lab'] = True
                                st.rerun()

            except Exception as e:
                st.error(f"❌ Błąd: {e}")

    # --- TAB 2: NOWA FUNKCJONALNOŚĆ (Laboratorium Tekstu) ---
    with tab_lab:
        st.header("✍️ Generator i Edytor Notatek")

        # Krótki opis dla użytkownika
        st.caption("Twórz profesjonalne notatki na podstawie transkrypcji. Wybierz styl, edytuj i eksportuj do Obsidian.")

        # Inicjalizacja session state dla edytowalnego wyniku
        if 'generated_content' not in st.session_state:
            st.session_state['generated_content'] = None
        if 'current_output_filename' not in st.session_state:
            st.session_state['current_output_filename'] = None

        # =====================================================
        # KROK 1: WYBÓR ŹRÓDŁA
        # =====================================================
        st.subheader("📂 Krok 1: Wybierz źródło danych")

        json_files = glob.glob(os.path.join(DATA_PROCESSED, "*.json"))
        json_files.sort(key=os.path.getmtime, reverse=True)

        if not json_files:
            st.info(
                "**Jak zacząć?**\n\n"
                "1. Przejdź do zakładki **📂 Przetwarzanie Audio**\n"
                "2. Wklej link YouTube lub wybierz plik lokalny\n"
                "3. Upewnij się, że opcja **Ekstrakcja wiedzy** jest zaznaczona\n"
                "4. Kliknij **Start** - po zakończeniu pliki JSON pojawią się tutaj automatycznie"
            )
        else:
            # Automatycznie wybierz ostatni plik z ekstrakcji jeśli istnieje
            default_index = 0
            if st.session_state.get('last_extraction_json'):
                last_json = st.session_state['last_extraction_json']
                if last_json in json_files:
                    default_index = json_files.index(last_json)

            # Pokaż komunikat jeśli przyszliśmy z przycisku "Przejdź do Laboratorium"
            if st.session_state.get('go_to_lab'):
                st.success("✨ Świeża baza wiedzy gotowa! Wybierz styl i wygeneruj notatkę.")
                st.session_state['go_to_lab'] = False

            selected_file = st.selectbox(
                "Baza wiedzy (plik JSON):",
                json_files,
                index=default_index,
                format_func=lambda x: os.path.basename(x)
            )

            if selected_file:
                # Ładowanie danych
                with open(selected_file, 'r', encoding='utf-8') as f:
                    knowledge_data = json.load(f)

                # =====================================================
                # P1: PODGLĄD KONTEKSTU
                # =====================================================
                # Zliczanie elementów
                all_concepts = []
                all_tools = []
                all_tips = []
                all_topics = set()

                for item in knowledge_data:
                    if 'key_concepts' in item:
                        all_concepts.extend(item['key_concepts'])
                    if 'tools' in item:
                        all_tools.extend(item['tools'])
                    if 'tips' in item:
                        all_tips.extend(item['tips'])
                    if 'topics' in item:
                        all_topics.update(item['topics'])

                # Metryki
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("📊 Segmenty", len(knowledge_data))
                col_m2.metric("💡 Pojęcia", len(all_concepts))
                col_m3.metric("🔧 Narzędzia", len(all_tools))
                col_m4.metric("📌 Wskazówki", len(all_tips))

                # Podgląd danych w expander
                with st.expander("🔍 Podgląd wyekstrahowanych danych", expanded=False):
                    preview_col1, preview_col2 = st.columns(2)

                    with preview_col1:
                        st.markdown("**Kluczowe pojęcia:**")
                        for concept in all_concepts[:5]:
                            st.markdown(f"- **{concept.get('term', 'N/A')}**: {concept.get('definition', '')[:80]}...")
                        if len(all_concepts) > 5:
                            st.caption(f"... i {len(all_concepts) - 5} więcej")

                    with preview_col2:
                        st.markdown("**Narzędzia:**")
                        for tool in all_tools[:5]:
                            st.markdown(f"- **{tool.get('name', 'N/A')}**: {tool.get('description', '')[:60]}...")
                        if len(all_tools) > 5:
                            st.caption(f"... i {len(all_tools) - 5} więcej")

                    st.markdown("**Tematy/Tagi:**")
                    st.write(", ".join(list(all_topics)[:15]))

                st.divider()

                # =====================================================
                # KROK 2: WYBÓR STYLU (P2: Radio buttons z opisami)
                # =====================================================
                st.subheader("🎨 Krok 2: Wybierz styl notatki")

                # Opisy stylów do wyświetlenia
                style_descriptions = {
                    "standard": "Zbalansowany, edukacyjny. TL;DR na górze, Wikilinks [[Termin]], krótkie akapity.",
                    "academic": "Formalny, analityczny. Pełne akapity prozy, głęboka analiza relacji, bogate słownictwo.",
                    "blog": "Luźny, bezpośredni. Emotikony, chwytliwe nagłówki, storytelling, praktyczne use-cases."
                }

                style_cols = st.columns(3)

                # Radio button dla wyboru stylu
                selected_mode = st.radio(
                    "Styl:",
                    options=list(PROMPT_TEMPLATES.keys()),
                    format_func=lambda x: PROMPT_TEMPLATES[x]["name"],
                    horizontal=True,
                    label_visibility="collapsed"
                )

                # Wyświetl opis wybranego stylu
                st.info(f"**{PROMPT_TEMPLATES[selected_mode]['name']}**: {style_descriptions.get(selected_mode, '')}")

                st.divider()

                # =====================================================
                # KROK 3: TEMAT
                # =====================================================
                st.subheader("📝 Krok 3: Temat notatki")

                # Użyj topic z session state (jeśli właśnie przyszedł z ekstrakcji) lub wyciągnij z nazwy pliku
                if st.session_state.get('last_topic_name') and st.session_state.get('last_extraction_json') == selected_file:
                    auto_topic = st.session_state['last_topic_name']
                else:
                    auto_topic = _extract_topic_from_filename(selected_file)

                topic_name = st.text_input("Temat:", value=auto_topic, label_visibility="collapsed")

                # =====================================================
                # P1: EXPANDER DLA PROMPTÓW (Zaawansowane)
                # =====================================================
                default_sys = PROMPT_TEMPLATES[selected_mode]["system"]
                default_user = PROMPT_TEMPLATES[selected_mode]["user"]

                with st.expander("⚙️ Zaawansowane: Edycja Promptów", expanded=False):
                    st.caption("Edytuj prompty tylko jeśli wiesz co robisz. Zmienne: `{topic_name}`, `{context_items}`")

                    edited_system = st.text_area(
                        "System Prompt (Rola AI):",
                        value=default_sys,
                        height=180,
                        key="system_prompt_editor"
                    )
                    edited_user = st.text_area(
                        "User Prompt (Zadanie):",
                        value=default_user,
                        height=120,
                        key="user_prompt_editor"
                    )

                    # Walidacja placeholderów
                    if "{context_items}" not in edited_user:
                        st.warning("⚠️ Brak `{context_items}` w User Prompt - notatka będzie bez danych źródłowych!")
                    if "{topic_name}" not in edited_user:
                        st.warning("⚠️ Brak `{topic_name}` w User Prompt - temat nie zostanie przekazany do LLM.")

                    col_reset, _ = st.columns([1, 3])
                    with col_reset:
                        if st.button("🔄 Przywróć domyślne", key="reset_prompts"):
                            st.rerun()

                st.divider()

                # =====================================================
                # PRZYCISK GENEROWANIA
                # =====================================================
                gen_col1, gen_col2 = st.columns([2, 1])
                with gen_col1:
                    generate_btn = st.button("🚀 Generuj Notatkę", type="primary", use_container_width=True)
                with gen_col2:
                    st.caption("Model: Bielik 11B (~30-60s)")

                if generate_btn:
                    writer = ReportWriter()

                    # Streaming z live preview
                    st.write("---")
                    st.write("🧠 **Bielik generuje notatkę...**")
                    stream_placeholder = st.empty()
                    stream_status = st.empty()

                    streamed_content = []
                    token_count = [0]  # Lista dla closure

                    def stream_to_ui(token: str):
                        """Callback wywoływany dla każdego tokena."""
                        streamed_content.append(token)
                        token_count[0] += 1

                        # Aktualizuj podgląd co 5 tokenów (dla wydajności)
                        if token_count[0] % 5 == 0:
                            stream_placeholder.markdown("".join(streamed_content) + "▌")
                            stream_status.caption(f"Generowanie... ({token_count[0]} tokenów)")

                    final_md = writer.generate_chapter(
                        topic_name=topic_name,
                        aggregated_data=knowledge_data,
                        mode=selected_mode,
                        custom_system_prompt=edited_system,
                        custom_user_prompt=edited_user,
                        stream_callback=stream_to_ui
                    )

                    # Wyczyść placeholdery po zakończeniu
                    stream_placeholder.empty()
                    stream_status.empty()

                    # Zapisz do session state
                    st.session_state['generated_content'] = final_md
                    st.session_state['current_output_filename'] = os.path.basename(selected_file).replace(".json", f"_{selected_mode}.md")
                    st.success(f"✅ Wygenerowano notatkę! ({token_count[0]} tokenów)")
                    st.rerun()

                # =====================================================
                # P2: EDYTOWALNY WYNIK PRZED ZAPISEM
                # =====================================================
                if st.session_state['generated_content']:
                    st.divider()
                    st.subheader("📝 Wynik (edytowalny)")

                    # Tabs dla podglądu vs edycji
                    view_tab, edit_tab = st.tabs(["👁️ Podgląd", "✏️ Edycja"])

                    with view_tab:
                        st.markdown(st.session_state['generated_content'])

                    with edit_tab:
                        edited_content = st.text_area(
                            "Edytuj markdown przed zapisem:",
                            value=st.session_state['generated_content'],
                            height=400,
                            key="result_editor",
                            label_visibility="collapsed"
                        )
                        # Aktualizuj session state jeśli edytowano
                        if edited_content != st.session_state['generated_content']:
                            st.session_state['generated_content'] = edited_content

                    # Przyciski akcji
                    st.divider()
                    action_col1, action_col2, action_col3, action_col4 = st.columns(4)

                    output_filename = st.session_state['current_output_filename']
                    save_path = os.path.join(DATA_OUTPUT, output_filename)
                    content_to_save = st.session_state['generated_content']

                    with action_col1:
                        if st.button("💾 Zapisz lokalnie", use_container_width=True):
                            with open(save_path, "w", encoding="utf-8") as f:
                                f.write(content_to_save)
                            st.success(f"Zapisano: {output_filename}")

                    with action_col2:
                        st.download_button(
                            "📥 Pobierz .md",
                            content_to_save,
                            file_name=output_filename,
                            use_container_width=True
                        )

                    with action_col3:
                        if obsidian_vault:
                            if st.button("📦 → Obsidian", use_container_width=True):
                                try:
                                    # Zapisz lokalnie najpierw
                                    with open(save_path, "w", encoding="utf-8") as f:
                                        f.write(content_to_save)
                                    shutil.copy(save_path, Path(obsidian_vault) / output_filename)
                                    st.success("Skopiowano do Obsidian!")
                                except Exception as e:
                                    st.error(f"Błąd: {e}")
                        else:
                            st.button("📦 → Obsidian", disabled=True, use_container_width=True, help="Ustaw ścieżkę Vault w sidebarze")

                    with action_col4:
                        if st.button("🗑️ Wyczyść", use_container_width=True):
                            st.session_state['generated_content'] = None
                            st.session_state['current_output_filename'] = None
                            st.rerun()

    # --- Logi na dole strony (w expander) ---
    with st.expander("📋 Logi systemowe", expanded=False):
        if os.path.exists("app_debug.log"):
            if st.button("🔄 Odśwież logi"):
                st.rerun()
            with open("app_debug.log", "r", encoding="utf-8") as f:
                logs = f.readlines()[-30:]
            st.code("".join(logs), language="log")
        else:
            st.caption("Brak pliku logów (app_debug.log)")


if __name__ == "__main__":
    main()
