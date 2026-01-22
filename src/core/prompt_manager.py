from dataclasses import dataclass
from typing import List, Optional

@dataclass
class PromptTemplate:
    role: str
    task: str
    constraints: List[str]
    style_guide: str

class PromptManager:
    def __init__(self):
        pass

    def build_writer_prompt(self, context_text: str, topic_name: str, content_type: str = "standard") -> str:
        """Dynamicznie buduje prompt dla Pisarza (Bielika)."""
        
        role = "Jesteś ekspertem technicznym i doświadczonym redaktorem technicznym."
        
        if content_type == "deep_dive":
            style = "Styl: Analityczny, głęboki, wyczerpujący temat, dążący do formy rozdziału w podręczniku."
        else:
            style = "Styl: Zwięzły, konkretny, merytoryczny."

        constraints = [
            "Używaj pogrubień dla kluczowych pojęć.",
            "Nie używaj wstępów typu 'W tym tekście omówię' ani 'Podsumowując'.",
            "Pisz wyłącznie w języku polskim.",
            "Opieraj się wyłącznie na dostarczonych danych (nie halucynuj).",
            "Używaj formatowania Markdown."
        ]

        # Składanie promptu
        prompt = f"""ROLA: {role}
ZADANIE: Napisz wysokiej jakości notatkę/rozdział na temat: {topic_name}
{style}

WYTYCZNE:
{chr(10).join(['- ' + c for c in constraints])}

KONTEKST (DANE WEJŚCIOWE):
{context_text}

MERYTORYCZNA TREŚĆ NOTATKI:
"""
        return prompt.strip()

    def build_tagging_prompt(self, analyzed_text: str) -> str:
        """Osobny prompt dla Taggera (dla Qwena)."""
        return f"""Jesteś ekspertem od organizacji wiedzy i systemów PKM (zgodnych z Obsidian).
ZADANIE: Przeanalizuj poniższy tekst i wygeneruj listę 5-10 tagów (słowa kluczowe).
WYTYCZNE:
- Formatu tylko lista po przecinku.
- Małe litery, bez spacji (używaj podkreślników, np. bezpieczeństwo_it).
- Bez żadnego dodatkowego tekstu, wstępów czy numeracji.

TEKST DO ANALIZY:
{analyzed_text}

TAGI:
"""

    def optimize_prompt_with_ai(self, raw_task: str) -> str:
        """
        [BETA] Placeholder dla przyszłej optymalizacji promptów przez AI.
        """
        # TODO: Implementacja w V2
        return raw_task
