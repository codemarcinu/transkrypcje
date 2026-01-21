import json
from src.core.llm_engine import call_ollama
from src.utils.config import MODEL_WRITER

def generate_chapter(topic_name: str, aggregated_data: list) -> str:
    """Faza REDUCE: Pisze rozdział na podstawie zebranych notatek w formacie Obsidian."""
    
    # 1. Agregacja metadanych do Frontmattera
    all_topics = set()
    all_tools = set()
    source_index = []
    
    context_str = ""
    for item in aggregated_data:
        # Zbieramy tagi
        if 'topics' in item:
            all_topics.update(item['topics'])
            
        # Zbieramy narzędzia (jako Wikilinks)
        if 'tools' in item and item['tools']:
            for t in item['tools']:
                all_tools.add(t['name'])
                context_str += f"- Narzędzie: [[{t['name']}]] - {t['description']}\n"
                
        # Zbieramy pojęcia (jako Wikilinks)
        if 'key_concepts' in item and item['key_concepts']:
            for c in item['key_concepts']:
                context_str += f"- Pojęcie: [[{c['term']}]] - {c['definition']}\n"
                
        # Wskazówki
        if 'tips' in item and item['tips']:
            for tip in item['tips']:
                context_str += f"- Wskazówka: {tip}\n"
                
        # Indeks źródłowy ( timestamp lub Part X)
        if 'time_range' in item:
            source_index.append(item['time_range'])

    # Formatowanie tagów dla YAML
    tags_yaml = [t.lower().replace(" ", "_") for t in list(all_topics)[:10]]
    
    system_prompt = """
    Jesteś architektem wiedzy (Knowledge Manager). Tworzysz notatki w formacie Obsidian Markdown.
    Piszesz w języku polskim.

    WYMAGANIA STRUKTURALNE:
    1. Na samym początku MUSI być blok YAML Frontmatter.
    2. Używaj "Wikilinks" (podwójne nawiasy [[ ]]) dla kluczowych pojęć i narzędzi.
    3. Styl: Zwięzły, techniczny, wypunktowany ("mięso" inżynierskie).
    4. Sekcja "## TL;DR" na początku (po YAML).
    5. Nie wymyślaj informacji spoza notatek.
    """
    
    source_index_str = "\n".join([f"- {m}" for m in source_index])
    
    user_prompt = f"""
    TEMAT: {topic_name}
    
    DANE WYJŚCIOWE:
    {context_str}
    
    Wypełnij YAML:
    ---
    tags: {tags_yaml}
    status: to_process
    type: training_note
    source: Sekurak Academy
    ---
    
    ZADANIE:
    Stwórz pełną notatkę w Markdown. 
    Używaj [[Linków]] dla narzędzi i pojęć.
    Na końcu dodaj sekcję:
    ## Indeks Źródłowy
    {source_index_str}
    """
    
    return call_ollama(
        model=MODEL_WRITER,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        json_mode=False
    )
