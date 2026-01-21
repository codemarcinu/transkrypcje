from datetime import datetime
from typing import Callable, Optional
from src.core.llm_engine import LLMEngine
from src.utils.prompts_config import PROMPT_TEMPLATES

class ReportWriter:
    def __init__(self):
        self.llm = LLMEngine(model_type="writer")

    def _prepare_context(self, aggregated_data: list) -> tuple[str, list]:
        """Przygotowuje kontekst i tagi z danych."""
        all_topics = set()
        context_lines = []

        for item in aggregated_data:
            if 'topics' in item and item['topics']:
                all_topics.update(item['topics'])

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
        return context_str, tags_list

    def _build_frontmatter(self, topic_name: str, tags_list: list, mode: str) -> str:
        """Generuje YAML frontmatter."""
        return f"""---
tags: {tags_list}
topic: "{topic_name}"
type: training_note
generator_mode: {mode}
created: {datetime.now().strftime('%Y-%m-%d %H:%M')}
---

"""

    def _build_source_index(self, aggregated_data: list) -> str:
        """Generuje indeks źródłowy."""
        source_index = "\n\n---\n## 📍 Indeks Źródłowy\n| Czas | Tematy |\n|---|---|\n"
        for item in aggregated_data:
            time_marker = item.get('time_range', 'N/A')
            topics = item.get('topics', [])[:3]
            combined = ", ".join(topics)
            if combined and time_marker:
                source_index += f"| **{time_marker}** | {combined} |\n"
        return source_index

    def generate_chapter(self, topic_name: str, aggregated_data: list,
                         mode: str = "standard",
                         custom_system_prompt: str = None,
                         custom_user_prompt: str = None,
                         stream_callback: Optional[Callable[[str], None]] = None) -> str:
        """
        Generuje notatkę z opcjonalnym streamingiem.

        Args:
            stream_callback: Funkcja wywoływana dla każdego tokena (np. do wyświetlania w GUI).
                             Jeśli None, używa standardowego generowania.
        """

        # 1. Przygotowanie danych
        context_str, tags_list = self._prepare_context(aggregated_data)

        # 2. Wybór szablonu
        template = PROMPT_TEMPLATES.get(mode, PROMPT_TEMPLATES["standard"])
        final_system_prompt = custom_system_prompt if custom_system_prompt else template["system"]
        raw_user_prompt = custom_user_prompt if custom_user_prompt else template["user"]
        final_user_prompt = raw_user_prompt.replace("{topic_name}", topic_name).replace("{context_items}", context_str)

        # 3. Generowanie treści
        print(f"--- GENEROWANIE NOTATKI (Tryb: {mode}) ---")

        if stream_callback:
            # Streaming mode - wyświetla tokeny w czasie rzeczywistym
            content_parts = []
            for token in self.llm.generate_stream(final_system_prompt, final_user_prompt):
                content_parts.append(token)
                stream_callback(token)
            content_response = "".join(content_parts)
        else:
            # Standard mode - czeka na całą odpowiedź
            content_response = self.llm.generate(final_system_prompt, final_user_prompt)

        # 4. Składanie dokumentu
        yaml_header = self._build_frontmatter(topic_name, tags_list, mode)
        source_index = self._build_source_index(aggregated_data)

        return yaml_header + content_response + source_index

# Wrapper dla kompatybilności
def generate_chapter(topic_name: str, aggregated_data: list, mode="standard") -> str:
    writer = ReportWriter()
    return writer.generate_chapter(topic_name, aggregated_data, mode=mode)
