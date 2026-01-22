"""
Batch API utilities - wspólne funkcje dla OpenAI Batch API.

Używane przez:
- src/gui/streamlit_app.py (Cloud Batch tab)
- nightly_pipeline.py (nocny pipeline)
"""

from typing import Dict
from src.utils.prompts_config import EXTRACTION_PROMPT
from src.utils.config import MODEL_EXTRACTOR_OPENAI


def build_batch_request(
    custom_id: str,
    transcript_text: str,
    model: str = MODEL_EXTRACTOR_OPENAI
) -> Dict:
    """
    Buduje pojedynczy request dla OpenAI Batch API w formacie JSONL.
    Używa scentralizowanego promptu z EXTRACTION_PROMPT.

    Args:
        custom_id: Unikalny identyfikator requestu (np. nazwa pliku).
        transcript_text: Tekst transkrypcji do analizy.
        model: Model OpenAI do użycia (domyślnie MODEL_EXTRACTOR_OPENAI).

    Returns:
        Dict zgodny z formatem OpenAI Batch API.

    Dokumentacja: https://platform.openai.com/docs/api-reference/batch
    """
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT["system"]},
                {"role": "user", "content": EXTRACTION_PROMPT["user"].format(text=transcript_text)}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }
    }
