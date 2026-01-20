import json
from src.core.llm_engine import call_ollama
from src.utils.config import MODEL_WRITER

def generate_chapter(topic_name: str, aggregated_data: list) -> str:
    """Faza REDUCE: Pisze rozdział na podstawie zebranych notatek."""
    
    # Przygotowanie kontekstu z wielu fragmentów JSON
    context_str = ""
    for item in aggregated_data:
        # Dodajemy narzędzia
        if 'tools' in item and item['tools']:
            for t in item['tools']:
                context_str += f"- Narzędzie: {t['name']} - {t['description']}\n"
        # Dodajemy pojęcia
        if 'key_concepts' in item and item['key_concepts']:
            for c in item['key_concepts']:
                context_str += f"- Pojęcie: {c['term']} - {c['definition']}\n"
        # Dodajemy porady
        if 'tips' in item and item['tips']:
            for tip in item['tips']:
                context_str += f"- Wskazówka: {tip}\n"

    system_prompt = """
    Jesteś profesjonalnym redaktorem podręczników IT. Piszesz w języku polskim.
    Twój styl jest:
    1. Konkretny i inżynierski (unikalny styl "mięsa" bez lania wody).
    2. Ustrukturyzowany (używasz Markdown, nagłówków, list).
    3. Edukacyjny (tłumaczysz trudne pojęcia).

    Zadanie: Napisz rozdział podręcznika na podany temat, korzystając TYLKO z dostarczonych notatek.
    Nie wymyślaj narzędzi, których nie ma w notatkach.
    """
    
    user_prompt = f"""
    TEMAT ROZDZIAŁU: {topic_name}
    
    DOSTĘPNE NOTATKI (ŹRÓDŁO):
    {context_str}
    
    Napisz teraz pełny rozdział w Markdown.
    """
    
    return call_ollama(
        model=MODEL_WRITER,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=False
    )
