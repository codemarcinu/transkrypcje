from src.core.llm_engine import call_ollama
from src.utils.config import MODEL_EXTRACTOR

def extract_knowledge(chunk_text: str) -> dict:
    """Faza MAP: Zamienia tekst na ustrukturyzowane dane."""
    system_prompt = """
    Jesteś analitykiem technicznym. Analizujesz transkrypcję szkolenia OSINT/Cybersec.
    Twoim celem jest wyciągnięcie twardych danych.
    
    Ignoruj: 
    - Sprawy organizacyjne ("czy słychać", "przerwa").
    - Żarty i dygresje niemerytoryczne.
    
    Wymagany format wyjściowy (JSON):
    {
        "topics": ["Temat A", "Temat B"],
        "tools": [
            {"name": "Nazwa Narzędzia", "description": "Do czego służy (precyzyjnie)", "url": "URL lub null"}
        ],
        "key_concepts": [
            {"term": "Pojęcie", "definition": "Definicja z tekstu"}
        ],
        "tips": ["Praktyczna porada 1", "Ostrzeżenie 2"]
    }
    """
    
    return call_ollama(
        model=MODEL_EXTRACTOR,
        system_prompt=system_prompt,
        user_prompt=f"Analizuj fragment:\n{chunk_text}",
        json_mode=True
    )
