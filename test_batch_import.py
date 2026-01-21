import os
import json
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.core.batch_manager import BatchManager
from src.utils.config import DATA_PROCESSED

def test_import():
    bm = BatchManager()
    
    # Mock data
    mock_results = [
        {
            "custom_id": "test_video.txt",
            "response": {
                "body": {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({
                                    "topics": ["OSINT", "Social Media"],
                                    "tools": [{"name": "Sherlock", "description": "Find usernames"}],
                                    "key_concepts": [{"term": "Doxing", "definition": "Searching for personal info"}],
                                    "tips": ["Use VPN"]
                                })
                            }
                        }
                    ]
                }
            }
        }
    ]
    
    print("Testing import_batch_to_lab...")
    imported = bm.import_batch_to_lab(mock_results)
    
    if "test_video_kb.json" in imported:
        print("✅ SUCCESS: File imported correctly.")
        kb_path = os.path.join(DATA_PROCESSED, "test_video_kb.json")
        with open(kb_path, 'r') as f:
            data = json.load(f)
            print(f"Imported content: {json.dumps(data, indent=2)}")
    else:
        print("❌ FAILURE: File not imported.")

if __name__ == "__main__":
    test_import()
