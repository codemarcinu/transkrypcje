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
        context_items = []
        
        # Zbieranie danych do promptu i indeksu
        for item in aggregated_data:
            # item to słownik zrzutowany z KnowledgeGraph
            if 'topics' in item and item['topics']:
                all_topics.update(item['topics'])
            
            # Budowanie kontekstu dla LLM (spłaszczanie wiedzy)
            if 'key_concepts' in item:
                for concept in item['key_concepts']:
                    context_items.append(f"- Pojęcie: {concept['term']} - {concept['definition']}")
            if 'tools' in item:
                for tool in item['tools']:
                    context_items.append(f"- Narzędzie: {tool['name']} - {tool['description']}")
            if 'tips' in item:
                for tip in item['tips']:
                    context_items.append(f"- Wskazówka: {tip}")

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
        system_prompt = """
        Jesteś Architektem Wiedzy (PKM Expert). Piszesz notatki w formacie Markdown zoptymalizowanym dla Obsidiana.
        
        WYMAGANIA:
        1. Używaj "Wikilinks" [[Termin]] dla kluczowych pojęć i narzędzi wymienionych w danych.
        2. Styl: Zwięzły, techniczny, wypunktowany.
        3. Sekcja "TL;DR" musi znaleźć się zaraz po tytule (pomijając YAML).
        4. NIE generuj nagłówka YAML ani H1 z tytułem pliku (zrobię to sam).
        """
        
        user_prompt = f"""
        TEMAT: {topic_name}
        
        DANE WSADOWE:
        {chr(10).join(context_items)}
        
        ZADANIE:
        Napisz treść notatki. Zacznij od nagłówka H2 (## Wstęp / TL;DR).
        Skup się na relacjach między pojęciami.
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
