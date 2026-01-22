"""
Sekurak Transcriber & Analyst v2.0 - Gradio UI

Pełne UI z trzema tabami:
- Tab 1: Nowa Transkrypcja (YouTube / pliki lokalne)
- Tab 2: Stwórz Notatkę (generowanie ze streamingiem)
- Tab 3: Przetwarzanie Zbiorcze (batch processing)
"""

import os
import gradio as gr

# Import konfiguracji
from src.utils.config import (
    WHISPER_LANGUAGES,
    WHISPER_MODELS,
    DEFAULT_MODEL_SIZE,
    DATA_OUTPUT,
    LLM_PROVIDER,
    OBSIDIAN_VAULT_PATH,
    OBSIDIAN_SUBFOLDER,
    OBSIDIAN_EXPORT_ENABLED,
)

# Import modułów GUI
from src.gui.theme import get_theme_and_css
from src.gui.constants import (
    LABELS,
    STYLE_CHOICES,
    STYLE_DESCRIPTIONS,
    OUTPUT_FORMAT_OPTIONS,
    SUMMARY_STYLE_OPTIONS,
    FILE_TYPES,
    DEFAULTS,
)
from src.gui.adapters import request_cancel, reset_cancel
from src.gui.handlers import (
    # Utility
    get_system_status,
    clear_vram,
    check_ollama_status,
    # Tab 1
    process_youtube,
    process_local_files,
    # Tab 2
    get_kb_files,
    load_kb_file,
    extract_topic_from_filename,
    generate_note_streaming,
    generate_tags_for_content,
    inject_tags_into_frontmatter,
    update_style_description,
    save_to_obsidian,
    save_note_locally,
    generate_filename_from_kb,
    # Tab 3
    count_urls,
    run_batch_wizard,
    # Navigation
    go_to_notes_tab,
    show_create_note_button,
)


def create_app() -> gr.Blocks:
    """
    Tworzy kompletną aplikację Gradio.

    Returns:
        gr.Blocks: Skonfigurowana aplikacja
    """
    theme, custom_css = get_theme_and_css()

    # Pobierz status systemu
    gpu_info, ffmpeg_info = get_system_status()

    # Domyślna ścieżka Obsidian
    default_obsidian = ""
    if OBSIDIAN_EXPORT_ENABLED:
        default_obsidian = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_SUBFOLDER)

    with gr.Blocks(title="Sekurak Transcriber & Analyst") as app:

        # =====================================================================
        # HEADER
        # =====================================================================
        with gr.Row():
            gr.Markdown(f"""
            # {LABELS['app_title']}
            *{LABELS['app_subtitle']}*
            """)

        # =====================================================================
        # MAIN LAYOUT
        # =====================================================================
        with gr.Row():

            # -----------------------------------------------------------------
            # SIDEBAR (scale=1)
            # -----------------------------------------------------------------
            with gr.Column(scale=1, variant="panel"):

                # Status systemu
                gr.Markdown(f"### {LABELS['system_status']}")
                gr.Markdown(gpu_info)
                gr.Markdown(ffmpeg_info)

                gr.Markdown("---")

                # Język
                language_dropdown = gr.Dropdown(
                    choices=list(WHISPER_LANGUAGES.keys()),
                    value=DEFAULTS["language"],
                    label=LABELS["language_label"]
                )

                # Ustawienia AI
                with gr.Accordion(LABELS["ai_settings"], open=False):
                    model_dropdown = gr.Dropdown(
                        choices=WHISPER_MODELS,
                        value=DEFAULTS["model_size"],
                        label=LABELS["model_label"],
                        info=LABELS["model_info"]
                    )
                    llm_provider_radio = gr.Radio(
                        choices=["ollama", "openai"],
                        value=LLM_PROVIDER,
                        label=LABELS["llm_provider_label"],
                        info=LABELS["llm_provider_info"]
                    )

                gr.Markdown("---")

                # Zadania
                gr.Markdown(f"### {LABELS['tasks_title']}")
                do_transcribe_cb = gr.Checkbox(
                    value=DEFAULTS["do_transcribe"],
                    label=LABELS["task_transcribe"]
                )
                do_extraction_cb = gr.Checkbox(
                    value=DEFAULTS["do_extract"],
                    label=LABELS["task_extract"]
                )
                do_summarize_cb = gr.Checkbox(
                    value=DEFAULTS["do_summarize"],
                    label=LABELS["task_summarize"]
                )

                gr.Markdown("---")

                # Opcje zaawansowane
                with gr.Accordion(LABELS["advanced_options"], open=False):
                    output_format_dropdown = gr.Dropdown(
                        choices=[label for _, label in OUTPUT_FORMAT_OPTIONS],
                        value="JSON (z metadanymi)",
                        label=LABELS["output_format_label"],
                        info=LABELS["output_format_info"]
                    )
                    download_subs_cb = gr.Checkbox(
                        value=DEFAULTS["download_subs"],
                        label=LABELS["download_subs_label"]
                    )
                    summary_style_dropdown = gr.Dropdown(
                        choices=SUMMARY_STYLE_OPTIONS,
                        value=DEFAULTS["summary_style"],
                        label=LABELS["summary_style_label"]
                    )
                    obsidian_vault_input = gr.Textbox(
                        value=default_obsidian,
                        label=LABELS["obsidian_vault_label"],
                        placeholder=LABELS["obsidian_vault_placeholder"]
                    )

                    # Ukryta ścieżka wyjściowa
                    output_path_input = gr.Textbox(
                        value=os.path.abspath(DATA_OUTPUT),
                        visible=False
                    )

                gr.Markdown("---")

                # Przyciski kontrolne
                with gr.Row():
                    clear_vram_btn = gr.Button(
                        LABELS["clear_vram_btn"],
                        variant="secondary",
                        size="sm"
                    )
                    cancel_btn = gr.Button(
                        LABELS["cancel_btn"],
                        variant="stop",
                        size="sm"
                    )

                vram_status = gr.Markdown("")

            # -----------------------------------------------------------------
            # MAIN CONTENT (scale=4)
            # -----------------------------------------------------------------
            with gr.Column(scale=4):
                with gr.Tabs() as tabs:

                    # =========================================================
                    # TAB 1: NOWA TRANSKRYPCJA
                    # =========================================================
                    with gr.Tab(LABELS["tab1_title"], id="tab_transcribe"):
                        gr.Markdown(f"## {LABELS['tab1_desc']}")
                        gr.Markdown(f"*{LABELS['tab1_hint']}*")

                        with gr.Row():
                            # YouTube
                            with gr.Column():
                                gr.Markdown(f"### {LABELS['youtube_section']}")
                                url_input = gr.Textbox(
                                    label=LABELS["youtube_url_label"],
                                    placeholder=LABELS["youtube_url_placeholder"],
                                    lines=1
                                )
                                start_yt_btn = gr.Button(
                                    LABELS["start_btn"],
                                    variant="primary",
                                    size="lg"
                                )

                            # Pliki lokalne
                            with gr.Column():
                                gr.Markdown(f"### {LABELS['local_section']}")
                                file_upload = gr.File(
                                    label=LABELS["local_file_label"],
                                    file_types=FILE_TYPES,
                                    file_count="multiple"
                                )
                                convert_mp3_cb = gr.Checkbox(
                                    value=True,
                                    label="Konwertuj na MP3",
                                    visible=False
                                )
                                start_local_btn = gr.Button(
                                    LABELS["start_btn"],
                                    variant="primary",
                                    size="lg"
                                )

                        gr.Markdown("---")

                        # Status i wyniki
                        status_output = gr.Textbox(
                            label=LABELS["status_log_label"],
                            lines=8,
                            max_lines=15,
                            interactive=False,
                            elem_id="status-log"
                        )

                        # Ukryte pola na ścieżki
                        with gr.Row(visible=False):
                            transcript_output = gr.Textbox(label="Transcript path")
                            kb_output = gr.Textbox(label="KB path")

                        # Przycisk do tworzenia notatki
                        create_note_btn = gr.Button(
                            LABELS["create_note_btn"],
                            variant="secondary",
                            size="lg",
                            visible=False
                        )

                    # =========================================================
                    # TAB 2: STWÓRZ NOTATKĘ
                    # =========================================================
                    with gr.Tab(LABELS["tab2_title"], id="tab_notes"):
                        gr.Markdown(f"## {LABELS['tab2_desc']}")

                        # Wybór pliku KB
                        with gr.Row():
                            kb_file_dropdown = gr.Dropdown(
                                choices=get_kb_files(),
                                label=LABELS["kb_file_label"],
                                interactive=True,
                                scale=5
                            )
                            refresh_files_btn = gr.Button(
                                LABELS["refresh_btn"],
                                scale=1,
                                size="sm"
                            )

                        # Główny przycisk generowania
                        generate_btn = gr.Button(
                            LABELS["generate_btn"],
                            variant="primary",
                            size="lg",
                            elem_classes=["primary-action"]
                        )

                        # Status generowania
                        generation_status = gr.Markdown(
                            "",
                            elem_id="generation-status"
                        )

                        # Dostosowanie notatki
                        with gr.Accordion(LABELS["customize_section"], open=True):
                            topic_input = gr.Textbox(
                                label=LABELS["topic_label"],
                                placeholder=LABELS["topic_placeholder"],
                                info=LABELS["topic_info"]
                            )

                            style_radio = gr.Radio(
                                choices=STYLE_CHOICES,
                                value=DEFAULTS["style"],
                                label=LABELS["style_label"],
                                info=LABELS["style_info"]
                            )

                            style_description = gr.Markdown(
                                f"*{STYLE_DESCRIPTIONS.get(DEFAULTS['style'], '')}*"
                            )

                            # Auto-tagowanie (TaggerAgent z Qwen)
                            auto_tag_cb = gr.Checkbox(
                                value=DEFAULTS.get("auto_tag", True),
                                label="Automatyczne tagowanie (Qwen)",
                                info="Wygeneruje tagi po zakonczeniu pisania notatki"
                            )

                        # Zaawansowane
                        with gr.Accordion(LABELS["advanced_section"], open=False):
                            # Metryki
                            gr.Markdown(f"**{LABELS['metrics_title']}**")
                            with gr.Row():
                                segments_metric = gr.Number(
                                    label=LABELS["segments_label"],
                                    value=0,
                                    interactive=False
                                )
                                concepts_metric = gr.Number(
                                    label=LABELS["concepts_label"],
                                    value=0,
                                    interactive=False
                                )
                                tools_metric = gr.Number(
                                    label=LABELS["tools_label"],
                                    value=0,
                                    interactive=False
                                )
                                tips_metric = gr.Number(
                                    label=LABELS["tips_label"],
                                    value=0,
                                    interactive=False
                                )

                            topics_display = gr.Textbox(
                                label="Wykryte tematy",
                                interactive=False,
                                lines=2
                            )

                            kb_preview = gr.Code(
                                label="Podglad JSON",
                                language="json",
                                lines=10
                            )

                            gr.Markdown("---")

                            # Metadane
                            gr.Markdown(f"**{LABELS['metadata_title']}**")
                            with gr.Row():
                                source_url_input = gr.Textbox(
                                    label=LABELS["source_url_label"],
                                    placeholder="https://..."
                                )
                                source_title_input = gr.Textbox(
                                    label=LABELS["source_title_label"]
                                )
                            with gr.Row():
                                duration_input = gr.Textbox(
                                    label=LABELS["duration_label"],
                                    placeholder="1:23:45"
                                )
                                aliases_input = gr.Textbox(
                                    label=LABELS["aliases_label"],
                                    placeholder="alias1, alias2"
                                )

                            gr.Markdown("---")

                            # Własne prompty
                            gr.Markdown(f"**{LABELS['custom_prompts_title']}**")
                            adv_system_prompt = gr.Textbox(
                                label=LABELS["system_prompt_label"],
                                lines=4
                            )
                            adv_user_prompt = gr.Textbox(
                                label=LABELS["user_prompt_label"],
                                lines=6
                            )
                            reset_prompts_btn = gr.Button(
                                LABELS["reset_prompts_btn"],
                                size="sm"
                            )

                        gr.Markdown("---")

                        # Output
                        with gr.Tabs():
                            with gr.TabItem(LABELS["preview_label"]):
                                preview_output = gr.Markdown(
                                    value="*Tutaj pojawi sie wygenerowana notatka...*",
                                    elem_id="preview-output"
                                )

                            with gr.TabItem(LABELS["edit_label"]):
                                edit_output = gr.Textbox(
                                    label="Edycja",
                                    lines=20,
                                    max_lines=50
                                )

                        # Tagi
                        tags_output = gr.Textbox(
                            label=LABELS["tags_label"],
                            value="Oczekiwanie na analize...",
                            interactive=False,
                            elem_classes=["tags-display"]
                        )

                        gr.Markdown("---")

                        # Zapis
                        gr.Markdown(f"### {LABELS['save_section']}")
                        with gr.Row():
                            output_filename_input = gr.Textbox(
                                label=LABELS["filename_label"],
                                placeholder="notatka.md",
                                scale=3
                            )
                            save_obsidian_btn = gr.Button(
                                LABELS["save_obsidian_btn"],
                                variant="primary",
                                scale=1
                            )
                            save_local_btn = gr.Button(
                                LABELS["save_local_btn"],
                                variant="secondary",
                                scale=1
                            )

                        save_status = gr.Markdown("")

                        download_file = gr.File(
                            label=LABELS["download_btn"],
                            visible=False
                        )

                    # =========================================================
                    # TAB 3: PRZETWARZANIE ZBIORCZE
                    # =========================================================
                    with gr.Tab(LABELS["tab3_title"], id="tab_batch"):
                        gr.Markdown(f"## {LABELS['tab3_desc']}")

                        # Input URLi
                        batch_urls_input = gr.Textbox(
                            label=LABELS["batch_urls_label"],
                            placeholder=LABELS["batch_urls_placeholder"],
                            lines=8
                        )

                        urls_count_display = gr.Markdown("0 URLi")

                        with gr.Row():
                            batch_model_dropdown = gr.Dropdown(
                                choices=WHISPER_MODELS,
                                value=DEFAULT_MODEL_SIZE,
                                label=LABELS["model_label"],
                                scale=2
                            )
                            batch_start_btn = gr.Button(
                                LABELS["batch_start_btn"],
                                variant="primary",
                                scale=1
                            )

                        batch_log_output = gr.Textbox(
                            label=LABELS["batch_log_label"],
                            lines=15,
                            max_lines=30,
                            interactive=False,
                            elem_id="status-log"
                        )

                        batch_results_output = gr.Code(
                            label="Wyniki JSON",
                            language="json",
                            lines=10
                        )

                        # Historia (opcjonalne)
                        with gr.Accordion(LABELS["batch_history_title"], open=False):
                            gr.Markdown("*Historia zadan batch - w przyszlej wersji*")

        # =====================================================================
        # EVENT HANDLERS
        # =====================================================================

        # --- Sidebar ---
        clear_vram_btn.click(
            fn=clear_vram,
            outputs=[vram_status]
        )

        cancel_btn.click(
            fn=request_cancel,
            outputs=[status_output]
        )

        # --- Tab 1: YouTube ---
        start_yt_btn.click(
            fn=reset_cancel,
            outputs=[]
        ).then(
            fn=process_youtube,
            inputs=[
                url_input, language_dropdown, model_dropdown, output_format_dropdown,
                do_transcribe_cb, do_extraction_cb, do_summarize_cb,
                download_subs_cb, summary_style_dropdown, output_path_input
            ],
            outputs=[status_output, transcript_output, kb_output],
            show_progress="full"
        ).then(
            fn=show_create_note_button,
            inputs=[kb_output],
            outputs=[create_note_btn]
        )

        # --- Tab 1: Pliki lokalne ---
        start_local_btn.click(
            fn=reset_cancel,
            outputs=[]
        ).then(
            fn=process_local_files,
            inputs=[
                file_upload, language_dropdown, model_dropdown, output_format_dropdown,
                do_transcribe_cb, do_extraction_cb, do_summarize_cb,
                convert_mp3_cb, summary_style_dropdown, output_path_input
            ],
            outputs=[status_output, transcript_output, kb_output],
            show_progress="full"
        ).then(
            fn=show_create_note_button,
            inputs=[kb_output],
            outputs=[create_note_btn]
        )

        # --- Tab 1 -> Tab 2: Przejście ---
        create_note_btn.click(
            fn=go_to_notes_tab,
            inputs=[kb_output],
            outputs=[
                kb_file_dropdown, tabs, topic_input,
                segments_metric, concepts_metric, tools_metric, tips_metric,
                topics_display, kb_preview
            ]
        )

        # --- Tab 2: Odśwież pliki KB ---
        refresh_files_btn.click(
            fn=lambda: gr.update(choices=get_kb_files()),
            outputs=[kb_file_dropdown]
        )

        # --- Tab 2: Załaduj plik KB ---
        kb_file_dropdown.change(
            fn=load_kb_file,
            inputs=[kb_file_dropdown],
            outputs=[
                segments_metric, concepts_metric, tools_metric, tips_metric,
                topics_display, kb_preview
            ]
        ).then(
            fn=generate_filename_from_kb,
            inputs=[kb_file_dropdown, style_radio],
            outputs=[output_filename_input]
        )

        # --- Tab 2: Zmiana stylu ---
        style_radio.change(
            fn=update_style_description,
            inputs=[style_radio],
            outputs=[style_description, adv_system_prompt, adv_user_prompt]
        ).then(
            fn=generate_filename_from_kb,
            inputs=[kb_file_dropdown, style_radio],
            outputs=[output_filename_input]
        )

        # --- Tab 2: Reset promptów ---
        reset_prompts_btn.click(
            fn=update_style_description,
            inputs=[style_radio],
            outputs=[style_description, adv_system_prompt, adv_user_prompt]
        )

        # --- Tab 2: Generowanie notatki (streaming) ---
        def start_generation():
            return (
                "Generuje notatke (Bielik)... moze potrwac 1-2 minuty",
                gr.update(interactive=False, value="Generuje..."),
                "Oczekiwanie na analize..."  # Reset tags
            )

        def start_tagging():
            return "Generuje tagi (Qwen)..."

        def finish_generation(content, tags_str):
            # Wstrzyknij tagi do frontmatter jeśli są
            final_content = inject_tags_into_frontmatter(content, tags_str)
            return (
                "",
                gr.update(interactive=True, value=LABELS["generate_btn"]),
                final_content,
                tags_str if tags_str else "Brak tagow"
            )

        generate_btn.click(
            fn=start_generation,
            outputs=[generation_status, generate_btn, tags_output]
        ).then(
            fn=generate_note_streaming,
            inputs=[
                kb_file_dropdown, style_radio, topic_input,
                adv_system_prompt, adv_user_prompt,
                source_url_input, source_title_input, duration_input, aliases_input
            ],
            outputs=[preview_output]
        ).then(
            fn=start_tagging,
            outputs=[generation_status]
        ).then(
            fn=generate_tags_for_content,
            inputs=[preview_output, auto_tag_cb],
            outputs=[tags_output]
        ).then(
            fn=finish_generation,
            inputs=[preview_output, tags_output],
            outputs=[generation_status, generate_btn, edit_output, tags_output]
        )

        # --- Tab 2: Zapis do Obsidian ---
        save_obsidian_btn.click(
            fn=save_to_obsidian,
            inputs=[edit_output, output_filename_input, obsidian_vault_input],
            outputs=[save_status]
        )

        # --- Tab 2: Zapis lokalny ---
        save_local_btn.click(
            fn=save_note_locally,
            inputs=[edit_output, output_filename_input],
            outputs=[save_status]
        )

        # --- Tab 3: Licznik URLi ---
        batch_urls_input.change(
            fn=count_urls,
            inputs=[batch_urls_input],
            outputs=[urls_count_display]
        )

        # --- Tab 3: Batch processing ---
        batch_start_btn.click(
            fn=reset_cancel,
            outputs=[]
        ).then(
            fn=run_batch_wizard,
            inputs=[batch_urls_input, batch_model_dropdown],
            outputs=[batch_log_output, batch_results_output],
            show_progress="full"
        )

    return app


def main():
    """Punkt wejścia aplikacji."""
    theme, custom_css = get_theme_and_css()
    app = create_app()
    app.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        inbrowser=True,
        theme=theme,
        css=custom_css
    )


if __name__ == "__main__":
    main()
