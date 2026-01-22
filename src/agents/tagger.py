from src.core.llm_engine import LLMEngine
from src.core.prompt_manager import PromptManager

class TaggerAgent:
    def __init__(self, provider: str = "ollama"):
        # Do tagowania Qwen (extractor) jest idealny
        self.llm = LLMEngine(model_type="extractor", provider=provider) 
        self.prompts = PromptManager()

    def generate_tags(self, text_content: str) -> list[str]:
        """Generuje listę tagów na podstawie treści."""
        prompt = self.prompts.build_tagging_prompt(text_content)
        
        # Wywołanie LLM bez formatu JSON (oczekujemy stringa po przecinku)
        response = self.llm.generate(
            system_prompt="Jesteś bibliotekarzem AI specjalizującym się w tagowaniu treści technicznych.", 
            user_prompt=prompt
        )
        
        # Czyszczenie i parsowanie
        if not response:
            return []
            
        # Obsługa ewentualnych list lub błędów formatowania
        tags = [t.strip().lower().replace(" ", "_") for t in response.split(',')]
        
        # Filtrowanie pustych i duplikatów
        unique_tags = []
        for tag in tags:
            if tag and tag not in unique_tags:
                unique_tags.append(tag)
                
        return unique_tags[:12] # Limitujemy do 
