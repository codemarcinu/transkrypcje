import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.core.llm_engine import LLMEngine
from src.utils.config import OPENAI_API_KEY

def test_openai():
    print("--- Test OpenAI Provider ---")
    if not OPENAI_API_KEY:
        print("❌ BŁĄD: Brak OPENAI_API_KEY w środowisku/konfiguracji.")
        return

    try:
        # Wymuszamy providera openai dla testu
        llm = LLMEngine(model_type="extractor", provider="openai")
        print(f"Model: {llm.model}")
        
        response = llm.generate(
            system_prompt="Jesteś pomocnym asystentem.",
            user_prompt="Powiedz cześć w dwóch słowach."
        )
        print(f"Odpowiedź: {response}")
        print("✅ OpenAI Real-time: OK")
    except Exception as e:
        print(f"❌ OpenAI Real-time Błąd: {e}")

if __name__ == "__main__":
    test_openai()
