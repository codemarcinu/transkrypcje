
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.core.batch_manager import BatchManager

def test_merging():
    manager = BatchManager()
    
    # Mock results from OpenAI Batch API
    results = [
        {
            "custom_id": "test_video__part_0",
            "response": {
                "body": {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps([{"segment": "Part 1 - Tool A", "narzedzia": ["Tool A"]}])
                            }
                        }
                    ]
                }
            }
        },
        {
            "custom_id": "test_video__part_1",
            "response": {
                "body": {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps([{"segment": "Part 2 - Tool B", "narzedzia": ["Tool B"]}])
                            }
                        }
                    ]
                }
            }
        },
        {
            "custom_id": "other_video",
            "response": {
                "body": {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps([{"segment": "Single part", "narzedzia": ["Tool C"]}])
                            }
                        }
                    ]
                }
            }
        }
    ]
    
    print("Testing import_batch_to_lab with chunked results...")
    imported_files = manager.import_batch_to_lab(results)
    print(f"Imported files: {imported_files}")
    
    assert "test_video_kb.json" in imported_files
    assert "other_video_kb.json" in imported_files
    
    # Verify content of test_video_kb.json
    kb_path = os.path.join("data/processed", "test_video_kb.json")
    with open(kb_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"Merged data length: {len(data)}")
    assert len(data) == 2
    assert data[0]["narzedzia"] == ["Tool A"]
    assert data[1]["narzedzia"] == ["Tool B"]
    
    print("Verification SUCCESSFUL!")

if __name__ == "__main__":
    test_merging()
