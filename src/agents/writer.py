from datetime import datetime
from typing import Callable, Optional
from src.core.llm_engine import LLMEngine
from src.utils.prompts_config import PROMPT_TEMPLATES

from datetime import datetime
from typing import Callable, Optional, List
from src.core.llm_engine import LLMEngine
from src.core.prompt_manager import PromptManager

class ReportWriter:
    def __init__(self):
        self.llm = LLMEngine(model_type="writer")
        self.prompt_manager = PromptManager()

    def _prepare_context(self, aggregated_data: list) -> str:
        """Przygotowuje kontekst z danych bazy wiedzy."""
        context_lines = []

        if not isinstance(aggregated_data, list):
            return ""

        for item in aggregated_data:
            if not isinstance(item, dict):
                continue

            if 'key_concepts' in item:
                for concept in item['key_concepts']:
                    if isinstance(concept, dict) and 'term' in concept and 'definition' in concept:
                        context_lines.append(f"- Pojęcie: {concept['term']} - {concept['definition']}")
            if 'tools' in item:
                for tool in item['tools']:
                    if isinstance(tool, dict) and 'name' in tool and 'description' in tool:
                        context_lines.append(f"- Narzędzie: {tool['name']} - {tool['description']}")
            if 'tips' in item:
                for tip in item['tips']:
                    context_lines.append(f"- Wskazówka: {tip}")

        return chr(10).join(context_lines)

    def _build_frontmatter(self, topic_name: str, tags_list: List[str], mode: str,
                           metadata: dict = None) -> str:
        """Generuje rozszerzony YAML frontmatter dla Obsidian."""
        meta = metadata or {}

        # Podstawowe pola
        lines = [
            "---",
            f"tags: {tags_list}",
            f'topic: "{topic_name}"',
        ]

        # Aliasy (opcjonalne)
        aliases = meta.get('aliases', [])
        if aliases:
            lines.append(f"aliases: {aliases}")

        # Źródło (opcjonalne)
        if meta.get('source_url'):
            lines.append(f'source_url: "{meta["source_url"]}"')
        if meta.get('source_title'):
            lines.append(f'source_title: "{meta["source_title"]}"')
        if meta.get('duration'):
            lines.append(f'duration: "{meta["duration"]}"')

        # Metadane systemowe
        lines.extend([
            f"type: training_note",
            f"generator_mode: {mode}",
            f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"reviewed: false",
            "---",
            "",
            ""
        ])

        return "\n".join(lines)

    def _build_source_index(self, aggregated_data: list) -> str:
        """Generuje indeks źródłowy z klikalnymi timestampami (Obsidian anchors)."""
        source_index = "\n\n---\n## 📍 Indeks Źródłowy\n| Czas | Tematy |\n|---|---|\n"

        if not isinstance(aggregated_data, list):
            return ""

        for item in aggregated_data:
            if not isinstance(item, dict):
                continue
            time_marker = item.get('time_range', 'N/A')
            topics = item.get('topics', [])[:3]
            combined = ", ".join(topics)
            if combined and time_marker:
                # Klikalne anchory w formacie Obsidian [[#anchor|display]]
                anchor_time = time_marker.replace(":", "-").replace(" ", "")
                source_index += f"| **[[#{anchor_time}|{time_marker}]]** | {combined} |\n"

        if source_index.count("|") <= 6:  # Tylko nagłówek (2 wiersze po 3 rury)
            return ""

        return source_index

    def generate_chapter(self, topic_name: str, aggregated_data: list,
                          mode: str = "standard",
                          tags: List[str] = None,
                          custom_system_prompt: str = None,
                          custom_user_prompt: str = None,
                          stream_callback: Optional[Callable[[str], None]] = None,
                          metadata: dict = None) -> str:
        """
        Generuje notatkę bez tagów wewnątrz (tagi przekazywane z zewnątrz).
        """
        # 0. Walidacja danych wejściowych
        if not isinstance(aggregated_data, list) or (len(aggregated_data) > 0 and not isinstance(aggregated_data[0], dict)):
            raise ValueError("Błąd: Dane wejściowe do ReportWriter muszą być listą obiektów JSON (Knowledge Base).")

        # 1. Przygotowanie danych
        context_str = self._prepare_context(aggregated_data)

        # 2. Budowa promptu przez PromptManager
        if custom_user_prompt:
             final_user_prompt = custom_user_prompt.replace("{topic_name}", topic_name).replace("{context_items}", context_str)
        else:
             final_user_prompt = self.prompt_manager.build_writer_prompt(context_str, topic_name, content_type=mode)

        final_system_prompt = custom_system_prompt if custom_system_prompt else "Jesteś ekspertem technicznym."

        # 3. Generowanie treści
        print(f"--- GENEROWANIE TREŚCI (Bielik) ---")

        if stream_callback:
            content_parts = []
            for token in self.llm.generate_stream(final_system_prompt, final_user_prompt):
                content_parts.append(token)
                stream_callback(token)
            content_response = "".join(content_parts)
        else:
            content_response = self.llm.generate(final_system_prompt, final_user_prompt)

        # 4. Składanie dokumentu
        tags_to_use = tags if tags is not None else []
        yaml_header = self._build_frontmatter(topic_name, tags_to_use, mode, metadata)
        source_index = self._build_source_index(aggregated_data)

        return yaml_header + content_response + source_index

# Wrapper dla kompatybilności
def generate_chapter(topic_name: str, aggregated_data: list, mode="standard") -> str:
    writer = ReportWriter()
    return writer.generate_chapter(topic_name, aggregated_data, mode=mode)
