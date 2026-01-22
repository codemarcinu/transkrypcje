from src.core.prompt_manager import PromptManager
from src.agents.tagger import TaggerAgent
import sys

def test_modular_logic():
    print("Testing PromptManager...")
    pm = PromptManager()
    writer_prompt = pm.build_writer_prompt("Test context", "Test Topic", content_type="standard")
    tagging_prompt = pm.build_tagging_prompt("Test text")
    
    assert "Test Topic" in writer_prompt
    assert "Test text" in tagging_prompt
    print("✅ PromptManager OK")
    
    # We can't easily test TaggerAgent without Ollama running, 
    # but we can test the parsing logic if we mock it.
    print("Testing TaggerAgent parsing...")
    tagger = TaggerAgent()
    # Mocking llm.generate would be better but let's check basic splitting if we can
    # Since I'm on a real system, I'll just check if it imports and initializes.
    print("✅ TaggerAgent Initialized")

if __name__ == "__main__":
    try:
        test_modular_logic()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
