import re
from src.core.llm_engine import LLMEngine
from src.core.prompt_manager import PromptManager
from src.utils.config import MODEL_TAGGER

class TaggerAgent:
    def __init__(self, provider: str = "ollama"):
        # Używamy dedykowanego modelu dla taggera
        self.llm = LLMEngine(model_type="extractor", model_name=MODEL_TAGGER, provider=provider) 
        self.prompts = PromptManager()

    def generate_tags(self, text_content: str) -> list[str]:
        """Generuje listę tagów na podstawie treści z agresywnym czyszczeniem."""
        prompt = self.prompts.build_tagging_prompt(text_content)
        
        # Wywołanie LLM z instrukcją systemową wymuszającą format
        response = self.llm.generate(
            system_prompt="Jesteś precyzyjnym asystentem. Odpowiadaj TYLKO listą słów kluczowych rozdzielonych przecinkami.", 
            user_prompt=prompt
        )
        
        if not response:
            return []

        # --- AGRESYWNE CZYSZCZENIE (Fix: Unikanie gadatliwości modelu) ---
        # 1. Usuń wszystko co nie jest literą, cyfrą, przecinkiem, myślnikiem lub spacją
        clean_response = re.sub(r'[^\w\s,\-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', '', response)
        
        # 2. Usuń wielokrotne spacje i zamień na małe litery
        clean_response = re.sub(r'\s+', ' ', clean_response).strip().lower()
        
        # 3. Podstawowy podział po przecinku
        tags = [t.strip().replace(" ", "_") for t in clean_response.split(',') if t.strip()]
        
        # 4. Fallback: Jeśli model użył nowej linii zamiast przecinka lub mamy śmieci
        if len(tags) <= 1 and '\n' in response:
             tags = [t.strip().lower().replace(" ", "_") for t in response.split('\n') if t.strip()]
             # Usuń bullet pointy (-, *, 1.)
             tags = [re.sub(r'^[\d\-\*\.]+\s*', '', t) for t in tags]

        # Filtrowanie duplikatów i pustych
        unique_tags = []
        for tag in tags:
            if tag and tag not in unique_tags:
                unique_tags.append(tag)
                
        return unique_tags[:10]  # Limit max 10 tagów
