from datetime import datetime
from src.core.llm_engine import LLMEngine

class ReportWriter:
    def __init__(self):
        self.llm = LLMEngine(model_type="writer")

    def generate_chapter(self, topic_name: str, aggregated_data: list) -> str:
        """
        Generuje notatkę w formacie Obsidian Markdown.
        """
        
        # 1. Przygotowanie danych do Frontmattera (Tagi)
        all_topics = set()
        
        # Uproszczona struktura danych JSON dla LLM (Opcja B)
        # Przekazujemy kluczowe informacje w strukturze, żeby model widział powiązania.
        simplified_data = []
        
        for item in aggregated_data:
            simplified_item = {}
            
            if 'topics' in item and item['topics']:
                all_topics.update(item['topics'])
                simplified_item['topics'] = item['topics']
            
            if 'key_concepts' in item:
                simplified_item['concepts'] = [
                    {"term": c['term'], "definition": c['definition']} 
                    for c in item['key_concepts']
                ]
            
            if 'tools' in item:
                simplified_item['tools'] = [
                    {"name": t['name'], "description": t['description']} 
                    for t in item['tools']
                ]
            
            if 'tips' in item:
                simplified_item['tips'] = item['tips']
                
            if simplified_item:
                simplified_data.append(simplified_item)

        # Ograniczenie liczby tagów do 10 najciekawszych (żeby nie spamować YAML)
        tags_list = [t.lower().replace(" ", "_") for t in list(all_topics)[:10]]
        
        # 2. Generowanie YAML Frontmatter (HARDCODED w Pythonie)
        # To gwarantuje, że Obsidian zawsze poprawnie odczyta metadane.
        yaml_header = f"""---
tags: {tags_list}
topic: "{topic_name}"
type: training_note
status: to_process
created: {datetime.now().strftime('%Y-%m-%d')}
source: "Sekurak Academy"
---

"""

        # 3. Wywołanie LLM dla treści głównej
        import json
        
        system_prompt = """
        Jesteś Architektem Wiedzy (PKM Expert) i Redaktorem Technicznym.
        Tworzysz pogłębione materiały szkoleniowe na podstawie surowych danych.

        WYMAGANIA:
        1. Używaj "Wikilinks" [[Termin]] dla kluczowych pojęć i narzędzi wymienionych w danych.
        2. STYL: Narracyjny, edukacyjny i szczegółowy. Unikaj nadmiernego punktowania faktów.
        3. Łącz fakty w związki przyczynowo-skutkowe (np. "Wynika z tego, że...", "W przeciwieństwie do...").
        4. Sekcja "TL;DR" ma być zwięzła, ale reszta notatki ma być wyczerpująca.
        5. GROUNDING: Korzystaj wyłącznie z dostarczonych danych. Jeśli czegoś nie ma w danych, nie zmyślaj.
        6. KRYTYCZNE: Używaj wyłącznie nagłówków poziomu 2 (##) i niższych. NIGDY nie używaj nagłówka poziomu 1 (#).
        7. NIE generuj nagłówka YAML (zrobię to sam).
        """
        
        user_prompt = f"""
        # TEMAT: {topic_name}
        
        DANE WSADOWE (JSON):
        {json.dumps(simplified_data, ensure_ascii=False, indent=2)}
        
        ZADANIE:
        Napisz rozbudowany rozdział podręcznika w Markdown.
        - Zacznij od nagłówka ## Wstęp / TL;DR.
        - Przeanalizuj relacje między pojęciami. 
        - Jeśli dane zawierają przykłady lub wskazówki, wpleć je w tekst akapitu, zamiast robić listę.
        - Wyjaśnij "dlaczego" dane pojęcie jest ważne w kontekście tematu.
        - Stwórz spójną narrację, unikaj suchego wymieniania po przecinku.
        """
        
        content_response = self.llm.generate(system_prompt, user_prompt)

        # 4. Generowanie Indeksu Źródłowego (Nowość!)
        # Tworzymy listę linków czasowych na dole notatki
        source_index = "\n\n---\n## 📍 Indeks Źródłowy\n"
        source_index += "| Czas | Tematy / Narzędzia |\n|---|---|\n"
        
        for item in aggregated_data:
            time_marker = item.get('time_range', 'N/A')
            # Filtrujemy puste wpisy
            topics = item.get('topics', [])[:3] # Max 3 tematy na linię
            tools = [t['name'] for t in item.get('tools', [])][:2] # Max 2 narzędzia
            
            combined_tags = ", ".join(topics + tools)
            if combined_tags and time_marker:
                 source_index += f"| **{time_marker}** | {combined_tags} |\n"

        # 5. Sklejenie wszystkiego w jeden plik
        final_document = yaml_header + content_response + source_index
        
        return final_document

# Wrapper dla zachowania kompatybilności wstecznej
def generate_chapter(topic_name: str, aggregated_data: list) -> str:
    writer = ReportWriter()
    return writer.generate_chapter(topic_name, aggregated_data)
