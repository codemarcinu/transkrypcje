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
        with open(file_path, "rb") as f:
            batch_file = self.client.files.create(
                file=f,
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
        Teraz obsługuje scalanie chunków (custom_id w formacie 'plik__part_N').
        """
        from collections import defaultdict
        
        # Grupowanie wyników według nazwy bazowej pliku
        grouped_results = defaultdict(list)
        
        for res in results:
            custom_id = res.get("custom_id", f"unknown_{int(time.time())}")
            
            # Obsługa formatu chunków: nazwa__part_0
            if "__part_" in custom_id:
                base_name = custom_id.split("__part_")[0]
            else:
                base_name = os.path.splitext(custom_id)[0]
            
            try:
                # Wyciągnięcie treści z odpowiedzi OpenAI
                content = res["response"]["body"]["choices"][0]["message"]["content"]
                
                # Proste czyszczenie markdowna
                if content.startswith("```json"):
                    content = content.replace("```json", "", 1).rsplit("```", 1)[0].strip()
                elif content.startswith("```"):
                    content = content.replace("```", "", 1).rsplit("```", 1)[0].strip()
                
                parsed_data = json.loads(content)
                
                # Upewnienie się, że mamy listę segmentów
                if isinstance(parsed_data, list):
                    grouped_results[base_name].extend(parsed_data)
                elif isinstance(parsed_data, dict):
                    # Jeśli model zwrócił jeden obiekt (np. z listami narzędzi/pojęć)
                    # to też pakujemy to w listę dla Laboratorium
                    grouped_results[base_name].append(parsed_data)
                    
            except Exception as e:
                print(f"[BATCH] Błąd parsowania dla {custom_id}: {e}")

        imported_files = []
        os.makedirs(DATA_PROCESSED, exist_ok=True)
        
        for base_name, kb_data in grouped_results.items():
            kb_filename = f"{base_name}_kb.json"
            kb_path = os.path.join(DATA_PROCESSED, kb_filename)
            
            try:
                # Jeśli plik już istnieje, wczytaj go i doklej (opcjonalne, ale bezpieczniejsze dla dużych batchy)
                # Na razie nadpisujemy/tworzymy nowy z całości zebranej w tym batchu
                with open(kb_path, "w", encoding="utf-8") as f:
                    json.dump(kb_data, f, ensure_ascii=False, indent=2)
                
                imported_files.append(kb_filename)
            except Exception as e:
                print(f"[BATCH] Błąd zapisu dla {base_name}: {e}")
                
        return imported_files
