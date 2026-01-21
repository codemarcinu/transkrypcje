from datetime import datetime
from src.core.llm_engine import LLMEngine
from src.utils.prompts_config import PROMPT_TEMPLATES # Import konfiguracji

class ReportWriter:
    def __init__(self):
        self.llm = LLMEngine(model_type="writer")

    def generate_chapter(self, topic_name: str, aggregated_data: list, 
                         mode: str = "standard", 
                         custom_system_prompt: str = None, 
                         custom_user_prompt: str = None) -> str:
        """
        Generuje notatkę, pozwalając na nadpisanie promptów (Custom Overrides).
        """
        
        # 1. Przygotowanie danych (Context Building)
        all_topics = set()
        context_lines = []
        
        for item in aggregated_data:
            if 'topics' in item and item['topics']:
                all_topics.update(item['topics'])
            
            # Budowanie kontekstu
            if 'key_concepts' in item:
                for concept in item['key_concepts']:
                    context_lines.append(f"- Pojęcie: {concept['term']} - {concept['definition']}")
            if 'tools' in item:
                for tool in item['tools']:
                    context_lines.append(f"- Narzędzie: {tool['name']} - {tool['description']}")
            if 'tips' in item:
                for tip in item['tips']:
                    context_lines.append(f"- Wskazówka: {tip}")

        context_str = chr(10).join(context_lines)
        tags_list = [t.lower().replace(" ", "_") for t in list(all_topics)[:10]]

        # 2. Wybór szablonu (Template Selection)
        # Jeśli użytkownik podał custom_prompt, używamy go. Jeśli nie, bierzemy z configu.
        template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["standard"])
        
        final_system_prompt = custom_system_prompt if custom_system_prompt else template["system"]
        raw_user_prompt = custom_user_prompt if custom_user_prompt else template["user"]

        # Wypełnianie zmiennych w User Prompt
        final_user_prompt = raw_user_prompt.replace("{topic_name}", topic_name).replace("{context_items}", context_str)

        # 3. Generowanie treści (LLM Call)
        print(f"--- GENEROWANIE NOTATKI (Tryb: {mode}) ---")
        content_response = self.llm.generate(final_system_prompt, final_user_prompt)

        # 4. Generowanie Frontmatter (Niezależne od promptu)
        yaml_header = f"""---
tags: {tags_list}
topic: "{topic_name}"
type: training_note
generator_mode: {mode}
created: {datetime.now().strftime('%Y-%m-%d %H:%M')}
---

"""

        # 5. Generowanie Indeksu Źródłowego (Kod bez zmian)
        source_index = "\n\n---\n## 📍 Indeks Źródłowy\n| Czas | Tematy |\n|---|---|\n"
        for item in aggregated_data:
            time_marker = item.get('time_range', 'N/A')
            topics = item.get('topics', [])[:3]
            combined = ", ".join(topics)
            if combined and time_marker:
                 source_index += f"| **{time_marker}** | {combined} |\n"

        return yaml_header + content_response + source_index

# Wrapper dla kompatybilności
def generate_chapter(topic_name: str, aggregated_data: list, mode="standard") -> str:
    writer = ReportWriter()
    return writer.generate_chapter(topic_name, aggregated_data, mode=mode)
