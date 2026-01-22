"""
Konfiguracja motywu Gradio dla Sekurak Transcriber & Analyst.
"""

import gradio as gr


def create_theme() -> gr.themes.Base:
    """
    Tworzy motyw aplikacji.

    Returns:
        Skonfigurowany motyw Gradio
    """
    return gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="gray",
        font=["Inter", "system-ui", "sans-serif"],
        font_mono=["JetBrains Mono", "Consolas", "monospace"],
    ).set(
        # Tło
        body_background_fill="#f8fafc",
        body_background_fill_dark="#0f172a",

        # Bloki
        block_background_fill="#ffffff",
        block_background_fill_dark="#1e293b",
        block_border_width="1px",
        block_border_color="#e2e8f0",
        block_border_color_dark="#334155",
        block_label_background_fill="#f1f5f9",
        block_label_background_fill_dark="#1e293b",
        block_shadow="0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",

        # Przyciski - Primary
        button_primary_background_fill="#2563eb",
        button_primary_background_fill_hover="#1d4ed8",
        button_primary_background_fill_dark="#3b82f6",
        button_primary_background_fill_hover_dark="#2563eb",
        button_primary_text_color="#ffffff",

        # Przyciski - Secondary
        button_secondary_background_fill="#f1f5f9",
        button_secondary_background_fill_hover="#e2e8f0",
        button_secondary_background_fill_dark="#334155",
        button_secondary_background_fill_hover_dark="#475569",
        button_secondary_text_color="#1e293b",
        button_secondary_text_color_dark="#f1f5f9",

        # Inputy
        input_background_fill="#ffffff",
        input_background_fill_dark="#1e293b",
        input_border_width="1px",
        input_border_color="#d1d5db",
        input_border_color_dark="#475569",
        input_border_color_focus="#2563eb",
        input_border_color_focus_dark="#3b82f6",

        # Tekst
        body_text_color="#1e293b",
        body_text_color_dark="#e2e8f0",
        body_text_size="14px",

        # Linki
        link_text_color="#2563eb",
        link_text_color_hover="#1d4ed8",
        link_text_color_dark="#60a5fa",

        # Checkbox/Radio
        checkbox_background_color="#ffffff",
        checkbox_background_color_dark="#1e293b",
        checkbox_border_color="#d1d5db",
        checkbox_border_color_dark="#475569",
        checkbox_border_color_selected="#2563eb",
        checkbox_border_color_selected_dark="#3b82f6",

        # Slider
        slider_color="#2563eb",
        slider_color_dark="#3b82f6",

        # Table
        table_border_color="#e2e8f0",
        table_border_color_dark="#334155",
        table_odd_background_fill="#f8fafc",
        table_odd_background_fill_dark="#1e293b",

        # Panel
        panel_background_fill="#f8fafc",
        panel_background_fill_dark="#0f172a",

        # Spacing
        layout_gap="16px",
        block_padding="16px",
        block_radius="8px",

        # Shadow
        shadow_drop="0 4px 6px -1px rgb(0 0 0 / 0.1)",
        shadow_drop_lg="0 10px 15px -3px rgb(0 0 0 / 0.1)",
    )


# Dodatkowe style CSS
CUSTOM_CSS = """
/* Status log - monospace font */
#status-log textarea {
    font-family: 'JetBrains Mono', Consolas, monospace !important;
    font-size: 12px !important;
    line-height: 1.5 !important;
}

/* Generation status */
#generation-status {
    color: #2563eb;
    font-weight: 500;
}

/* Primary action buttons */
.primary-action {
    min-height: 48px !important;
    font-size: 16px !important;
}

/* Tags display */
.tags-display textarea {
    background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%) !important;
    border: 1px solid #bfdbfe !important;
}

/* Metrics display */
.metric-box {
    text-align: center;
    padding: 12px;
    background: #f8fafc;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
}

.metric-value {
    font-size: 24px;
    font-weight: 600;
    color: #2563eb;
}

.metric-label {
    font-size: 12px;
    color: #64748b;
    margin-top: 4px;
}

/* Preview markdown */
#preview-output {
    max-height: 500px;
    overflow-y: auto;
}

/* Sidebar styling */
.sidebar-section {
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e2e8f0;
}

/* Tab styling */
.tab-nav button {
    font-weight: 500 !important;
}

.tab-nav button.selected {
    border-bottom: 2px solid #2563eb !important;
}

/* Accordion headers */
.label-wrap {
    font-weight: 500 !important;
}

/* File upload area */
.upload-button {
    border: 2px dashed #d1d5db !important;
    border-radius: 8px !important;
    transition: border-color 0.2s !important;
}

.upload-button:hover {
    border-color: #2563eb !important;
}

/* Progress bar */
.progress-bar {
    background: linear-gradient(90deg, #2563eb 0%, #3b82f6 100%) !important;
}

/* Streaming output animation */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.streaming-indicator {
    animation: pulse 1.5s ease-in-out infinite;
}

/* Dark mode adjustments */
@media (prefers-color-scheme: dark) {
    .tags-display textarea {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
        border: 1px solid #334155 !important;
    }

    .metric-box {
        background: #1e293b;
        border-color: #334155;
    }

    .metric-value {
        color: #60a5fa;
    }

    .metric-label {
        color: #94a3b8;
    }
}
"""


def get_theme_and_css():
    """
    Zwraca motyw i CSS do użycia w gr.Blocks().

    Returns:
        tuple: (theme, css_string)
    """
    return create_theme(), CUSTOM_CSS
