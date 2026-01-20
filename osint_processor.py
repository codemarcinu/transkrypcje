import os
import json
import re
import time
from typing import List
import ollama

import subprocess

# KONFIGURACJA
CONFIG = {
    "input_file": "Narzędziownik OSINT 2.0 Reloaded - sesja 6_transkrypcja.txt",
    "output_file": "RAPORT_OSINT_FINAL.md",
    "model_logic": "qwen2.5:14b",
    "model_style": "qwen2.5:14b",
    "chunk_size": 12000,
    "overlap": 1000
}

def get_wsl_host_ip() -> str:
    """Pobiera IP hosta Windows z poziomu WSL."""
    try:
        # Wyciąga IP bramy domyślnej
        cmd = "ip route show | grep default | awk '{print $3}'"
        return subprocess.check_output(cmd, shell=True).decode().strip()
    except Exception:
        return "127.0.0.1"

class TranscriptAgent:
    def __init__(self, config: dict):
        self.config = config
        host_ip = get_wsl_host_ip()
        print(f" [INFO] Wykryto IP hosta: {host_ip}")
        self.client = ollama.Client(host=f'http://{host_ip}:11434')

    def _clean_text(self, text: str) -> str:
        print(" [1/4] Czyszczenie i normalizacja tekstu...")
        text = re.sub(r'\[\d{2,3}:\d{2}\s->\s\d{2,3}:\d{2}\]', '', text) # Timestamps
        text = re.sub(r'\'', '', text) # Metadata
        return re.sub(r'\s+', ' ', text).strip()

    def _create_chunks(self, text: str) -> List[str]:
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = start + self.config["chunk_size"]
            chunks.append(text[start:end])
            start += self.config["chunk_size"] - self.config["overlap"]
        print(f" [INFO] Tekst podzielono na {len(chunks)} fragmentów (Chunk size: {self.config['chunk_size']}).")
        return chunks

    def _analyze_chunk(self, chunk: str, idx: int, total: int) -> str:
        prompt = f"""
        Jesteś analitykiem cyberbezpieczeństwa. Przeanalizuj ten fragment transkrypcji i wyodrębnij kluczowe informacje:
        
        1. **Narzędzia i URLe**: Wypisz nazwy narzędzi, stron i oprogramowania (wraz z kontekstem do czego służą).
        2. **Case Studies / Historie**: Streść krótko konkretne przykłady i historie opowiedziane przez prelegenta (np. wpadki AI, konkretne ataki, scamy). To jest BARDZO WAŻNE.
        3. **Techniki i Wiedza**: Jakie techniki OSINT lub manipulacji są omawiane? (np. deepfake, face swap, gaslighting).
        
        Format: Szczegółowe notatki w punktach. Zachowaj nazwy własne.
        
        FRAGMENT:
        {chunk}
        """
        print(f" [2/4] Mapowanie (Qwen): Analiza fragmentu {idx+1}/{total}...")
        try:
            response = self.client.chat(
                model=self.config["model_logic"],
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_ctx': 8192}
            )
            return response['message']['content']
        except Exception as e:
            print(f" [ERR] Błąd: {e}")
            return ""

    def _synthesize_report(self, notes: str) -> str:
        print(" [3/4] Redukcja (Bielik): Generowanie finalnego raportu (może potrwać chwilę przy ładowaniu modelu)...")
        system_prompt = "Jesteś ekspertem cyberbezpieczeństwa. Piszesz profesjonalny raport w języku polskim."
        user_prompt = f"""
        Stwórz profesjonalny, angażujący RAPORT BRANŻOWY na temat OSINT i AI w cyberbezpieczeństwie, oparty na dostarczonych notatkach.
        
        WAŻNE WYTYCZNE:
        1. **Konkretne Przykłady**: Raport musi zawierać omawiane w tekście historie (Case Studies), np. wpadki konkretnych modeli AI, historie ataków. To buduje wartość.
        2. **Fakty**: Opieraj się TYLKO na notatkach. Nie zmyślaj.
        3. **Źródła**: Wymień tylko te domeny/linki, które faktycznie padły w transkrypcji.

        STRUKTURA MARKDOWN:
        # [Chwytliwy Tytuł Raportu]
        
        ## 1. Wstęp
        Krótkie wprowadzenie do tematyki sesji (AI, Dezinformacja, OSINT).
        
        ## 2. Case Studies: Historie z Frontu
        Opisz najciekawsze przypadki omówione w materiale (np. Scamy, Deepfake'i polityków, Błędy AI).
        
        ## 3. Arsenał Narzędzi
        Wymień narzędzia w formie czytelnej listy lub tabeli (Nazwa | Zastosowanie).
        
        ## 4. Techniki Manipulacji i Obrony
        Omówienie technik (np. Gaslighting, Astroturfing) wspomnianych w tekście.
        
        ## 5. Wnioski
        Podsumowanie sesji.
        
        ## Źródła
        (Tylko zweryfikowane linki z tekstu)
        
        NOTATKI:
        {notes}
        """
        response = self.client.chat(
            model=self.config["model_style"],
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            options={'temperature': 0.6}
        )
        return response['message']['content']

    def run(self):
        if not os.path.exists(self.config["input_file"]):
            print(f" [STOP] Brak pliku: {self.config['input_file']}")
            return

        with open(self.config["input_file"], 'r', encoding='utf-8') as f:
            raw = f.read()

        clean = self._clean_text(raw)
        chunks = self._create_chunks(clean)
        
        if os.path.exists("intermediate_notes.json"):
            print(" [INFO] Znaleziono zapisane notatki. Wczytywanie...")
            with open("intermediate_notes.json", "r", encoding="utf-8") as f:
                notes = json.load(f)
        else:
            notes = []
            for i, chunk in enumerate(chunks):
                notes.append(self._analyze_chunk(chunk, i, len(chunks)))
            
            with open("intermediate_notes.json", "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False, indent=2)
            print(" [INFO] Zapisano notatki pośrednie.")

        full_notes = "\n".join(notes)
        final_md = self._synthesize_report(full_notes)

        with open(self.config["output_file"], "w", encoding="utf-8") as f:
            f.write(final_md)
        print(f" [4/4] Gotowe! Raport zapisano w: {self.config['output_file']}")

if __name__ == "__main__":
    TranscriptAgent(CONFIG).run()
