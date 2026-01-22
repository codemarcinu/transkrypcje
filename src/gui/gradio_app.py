import gradio as gr
import os
import asyncio
from src.core.processor import Processor
from src.utils.logger import logger
from src.utils.config import DATA_OUTPUT

# --- BRIDGE FUNCTION (Mostek między GUI a nowym Processorem) ---
def run_analysis(url, file, style, auto_tag):
    """
    Funkcja wrapper, która tłumaczy kliknięcia w GUI na logikę backendu.
    """
    # 1. Walidacja wejścia
    source = url if url else file
    if not source:
        return "❌ Błąd: Podaj link URL lub wgraj plik.", "", "", None

    # 2. Mapowanie stylu z GUI na klucze PromptManagera
    style_map = {
        "Standardowa Notatka": "note",
        "Deep Dive (Szczegółowy)": "deep_dive",
        "Streszczenie Exec": "summary",
        "Tylko Tagi": "tags_only"
    }
    selected_style = style_map.get(style, "note")

    status_log = "🚀 Inicjalizacja procesu...\n"
    yield status_log, "", "", None

    try:
        # 3. Uruchomienie Processora
        # Mocking progress/logger for the UI
        class ProgressLogger:
            def __init__(self, current_log):
                self.current_log = current_log
            def log(self, message):
                self.current_log += f"{message}\n"
                # Note: yield won't work from inside a method easily without more complexity
                # but we can at least log to terminal
                print(message)
        
        pg_logger = ProgressLogger(status_log)
        processor = Processor(logger=pg_logger, stop_event=None, progress_callback=None)
        
        status_log += f"📥 Pobieranie/Wczytywanie: {source}\n"
        yield status_log, "...", "...", None
        
        # Uruchomienie głównej rury
        result = processor.process_workflow(
            source=source, 
            prompt_style=selected_style, 
            enable_tagging=auto_tag
        )

        status_log += "✅ Przetwarzanie zakończone sukcesem!\n"
        
        # 4. Przygotowanie wyników
        content = result.get("content", "")
        tags = result.get("tags", [])
        output_file = result.get("file_path", "")
        
        # Formatowanie tagów dla Gradio (Label lub Textbox)
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)

        yield status_log, content, tags_str, output_file

    except Exception as e:
        error_msg = f"❌ Błąd krytyczny: {str(e)}"
        logger.error(error_msg)
        yield status_log + "\n" + error_msg, "BŁĄD", "BŁĄD", None


# --- GUI DEFINITION ---
def create_ui():
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
    ).set(
        body_background_fill="#f9fafb",
        block_background_fill="#ffffff"
    )

    with gr.Blocks(title="Sekurak Transcriber AI", theme=theme) as app:
        
        # Header
        with gr.Row():
            gr.Markdown("""
            # 🕵️ Sekurak Transcriber & Analyst (Modular)
            *Wydajne przetwarzanie lokalne: Whisper + Bielik (Writer) + Qwen (Tagger)*
            """)

        with gr.Row():
            # --- LEWA KOLUMNA: INPUT & CONTROL ---
            with gr.Column(scale=1, variant="panel"):
                gr.Markdown("### 1. Źródło")
                with gr.Tabs():
                    with gr.TabItem("YouTube / URL"):
                        url_input = gr.Textbox(
                            label="Link do materiału", 
                            placeholder="https://www.youtube.com/watch?v=..."
                        )
                    with gr.TabItem("Plik Lokalny"):
                        file_input = gr.File(
                            label="Plik Audio/Video", 
                            type="filepath"
                        )

                gr.Markdown("### 2. Konfiguracja Analizy")
                
                # Nowość: Wybór stylu (dzięki PromptManager)
                style_dropdown = gr.Dropdown(
                    choices=["Standardowa Notatka", "Deep Dive (Szczegółowy)", "Streszczenie Exec"],
                    value="Standardowa Notatka",
                    label="Styl Opracowania",
                    info="Wybierz jak Bielik ma sformatować treść."
                )

                # Nowość: Osobna kontrola tagowania
                with gr.Accordion("Opcje Dodatkowe", open=False):
                    auto_tag_checkbox = gr.Checkbox(
                        value=True, 
                        label="Automatyczne Tagowanie (Qwen)",
                        info="Wyłącz, aby przyspieszyć proces (pominie etap analizy słów kluczowych)."
                    )

                process_btn = gr.Button("🚀 Rozpocznij Analizę", variant="primary", size="lg")
                
                # Log statusu
                status_box = gr.Textbox(
                    label="Dziennik Zdarzeń", 
                    lines=6, 
                    max_lines=10,
                    interactive=False,
                    elem_id="status-log"
                )

            # --- PRAWA KOLUMNA: OUTPUT ---
            with gr.Column(scale=2):
                gr.Markdown("### 3. Wyniki")
                
                with gr.Group():
                    # Sekcja Tagów (wyróżniona)
                    tags_output = gr.Label(
                        label="🏷️ Wykryte Tagi",
                        value="Oczekiwanie na analizę...",
                        color="blue"
                    )
                    
                    # Główna treść
                    markdown_output = gr.Markdown(
                        label="Treść Notatki",
                        value="_Tutaj pojawi się wygenerowana notatka..._",
                        show_copy_button=True
                    )

                download_btn = gr.File(label="📂 Pobierz gotowy plik (.md / .json)")

        # --- WIRING (Podłączenie akcji) ---
        process_btn.click(
            fn=run_analysis,
            inputs=[url_input, file_input, style_dropdown, auto_tag_checkbox],
            outputs=[status_box, markdown_output, tags_output, download_btn]
        )

    return app

if __name__ == "__main__":
    ui = create_ui()
    ui.queue().launch(
        server_name="0.0.0.0", 
        server_port=7860, 
        inbrowser=True,
        share=False
    )
