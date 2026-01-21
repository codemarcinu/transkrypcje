import json
import os
import time
from typing import List, Dict
from openai import OpenAI
from src.utils.config import OPENAI_API_KEY, DATA_PROCESSED

class BatchManager:
    """Zarządza operacjami OpenAI Batch API."""
    
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def create_batch_file(self, requests: List[Dict], filename: str) -> str:
        """
        Tworzy plik .jsonl z listą żądań.
        requests: lista słowników { "custom_id": str, "method": "POST", "url": "/v1/chat/completions", "body": {...} }
        """
        file_path = os.path.join(DATA_PROCESSED, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            for req in requests:
                f.write(json.dumps(req, ensure_ascii=False) + "\n")
        return file_path

    def upload_and_submit(self, file_path: str, description: str = "Batch Job") -> str:
        """Przesyła plik i uruchamia Batch."""
        batch_file = self.client.files.create(
            file=open(file_path, "rb"),
            purpose="batch"
        )
        
        batch_job = self.client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": description}
        )
        return batch_job.id

    def list_active_batches(self):
        """Pobiera listę ostatnich batchy."""
        return self.client.batches.list(limit=10)

    def retrieve_results(self, batch_id: str) -> List[Dict]:
        """Pobiera wyniki ukończonego batcha."""
        batch = self.client.batches.retrieve(batch_id)
        if batch.status != "completed":
            print(f"[BATCH] Status: {batch.status}. Jeszcze nie ukończono.")
            return []

        # Pobranie pliku wynikowego
        output_file_id = batch.output_file_id
        file_response = self.client.files.content(output_file_id)
        
        results = []
        for line in file_response.text.splitlines():
            results.append(json.loads(line))
        
        return results

    def cancel_batch(self, batch_id: str):
        """Anuluje batch."""
        return self.client.batches.cancel(batch_id)

    def import_batch_to_lab(self, results: List[Dict]) -> List[str]:
        """
        Przekształca wyniki Batcha w pliki _kb.json gotowe dla Laboratorium.
        """
        imported_files = []
        for res in results:
            custom_id = res.get("custom_id", f"unknown_{int(time.time())}")
            # custom_id to zazwyczaj nazwa pliku wejściowego (np. plik.txt)
            base_name = os.path.splitext(custom_id)[0]
            kb_filename = f"{base_name}_kb.json"
            kb_path = os.path.join(DATA_PROCESSED, kb_filename)
            
            try:
                # Wyciągnięcie treści z odpowiedzi OpenAI
                content = res["response"]["body"]["choices"][0]["message"]["content"]
                
                # Proste czyszczenie markdowna jeśli model go dodał
                if content.startswith("```json"):
                    content = content.replace("```json", "", 1).rsplit("```", 1)[0].strip()
                elif content.startswith("```"):
                    content = content.replace("```", "", 1).rsplit("```", 1)[0].strip()
                
                # Parsowanie treści jako JSON (powinna to być lista obiektów KnowledgeGraph)
                # UWAGA: Batch zazwyczaj analizuje jeden duży chunk lub cały plik.
                # Laboratorium oczekuje listy segmentów, więc pakujemy to w listę.
                parsed_at_source = json.loads(content)
                
                # Jeśli to nie jest lista, opakuj w listę (Laboratorium obsługuje listę segmentów)
                if not isinstance(parsed_at_source, list):
                    kb_data = [parsed_at_source]
                else:
                    kb_data = parsed_at_source
                
                os.makedirs(DATA_PROCESSED, exist_ok=True)
                with open(kb_path, "w", encoding="utf-8") as f:
                    json.dump(kb_data, f, ensure_ascii=False, indent=2)
                
                imported_files.append(kb_filename)
            except Exception as e:
                print(f"[BATCH] Błąd importu dla {custom_id}: {e}")
                
        return imported_files
