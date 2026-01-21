import sys
import os
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.agents.writer import ReportWriter
from src.utils.prompts_config import PROMPT_TEMPLATES

def test_writer():
    writer = ReportWriter()
    
    # Dummy data
    aggregated_data = [
        {
            "time_range": "00:00:01",
            "topics": ["Firewalls", "Network Security"],
            "key_concepts": [{"term": "Stateful Inspection", "definition": "A technique that tracks the connection state."}],
            "tools": [{"name": "iptables", "description": "Linux firewall utility."}],
            "tips": ["Always use default deny rule."]
        }
    ]
    
    print("Testing Standard Mode...")
    standard_note = writer.generate_chapter("Basic Networking", aggregated_data, mode="standard")
    print(f"Standard Note Length: {len(standard_note)}")
    assert "📘 Podręcznik (Standard)" in PROMPT_TEMPLATES["standard"]["name"]
    assert "generator_mode: standard" in standard_note
    
    print("Testing Academic Mode...")
    academic_note = writer.generate_chapter("Basic Networking", aggregated_data, mode="academic")
    print(f"Academic Note Length: {len(academic_note)}")
    assert "generator_mode: academic" in academic_note

    print("Testing Custom Prompt...")
    custom_sys = "Jesteś piratem. Pisz jak pirat. ARR!"
    custom_user = "TEMAT: {topic_name}. DANE: {context_items}. Pisz!"
    custom_note = writer.generate_chapter("Pirate Security", aggregated_data, custom_system_prompt=custom_sys, custom_user_prompt=custom_user)
    print(f"Custom Note Content Snippet: {custom_note[:200]}")
    # We can't easily verify the LLM output content matches "pirate" without running it, 
    # but we can verify it doesn't crash and includes the correct frontmatter.
    assert "topic: \"Pirate Security\"" in custom_note

    print("Verification Script Finished Successfully (Logic Check Only - LLM calls may vary).")

if __name__ == "__main__":
    try:
        test_writer()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
