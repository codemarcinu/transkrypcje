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
