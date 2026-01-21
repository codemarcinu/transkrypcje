import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.agents.extractor import extract_knowledge
from src.agents.writer import generate_chapter
from src.core.schema import KnowledgeGraph

def test_extractor():
    print("Testing Extractor with retry logic and time_range...")
    text = "W tym module omówimy narzędzie Maltego. Maltego służy do analizy powiązań."
    time_tag = "Part 1 (10%)"
    
    result = extract_knowledge(text, time_range=time_tag)
    print(f"Result time_range: {result.time_range}")
    print(f"Found tools: {[t.name for t in result.tools]}")
    
    assert result.time_range == time_tag
    assert len(result.tools) > 0
    print("Extractor test passed!\n")
    return result

def test_writer(knowledge_data):
    print("Testing Writer with Obsidian format...")
    topic = "Testowy Kurs OSINT"
    
    # knowledge_data is a KnowledgeGraph object, we need a list of dicts for generate_chapter
    aggregated_data = [knowledge_data.model_dump()]
    
    markdown_output = generate_chapter(topic, aggregated_data)
    
    print("Markdown Preview (first 200 chars):")
    print(markdown_output[:200])
    
    # Check for Obsidian features
    assert "---" in markdown_output  # YAML
    assert "tags:" in markdown_output # YAML tags
    assert "[[" in markdown_output # Wikilinks
    assert "## Indeks Źródłowy" in markdown_output
    
    print("\nWriter test passed!")

if __name__ == "__main__":
    try:
        kb_result = test_extractor()
        test_writer(kb_result)
        print("\n✅ All tests passed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
