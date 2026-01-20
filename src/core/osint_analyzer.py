import os
import json
import re
import requests
import time
from typing import List
import ollama
from src.utils.config import OLLAMA_URL

class OsintAnalyzer:
    def __init__(self, logger=None, stop_event=None, progress_callback=None):
        self.logger = logger
        self.stop_event = stop_event
        self.progress_callback = progress_callback
        
        # Parse host from full URL for ollama client (it expects base URL usually, but let's see)
        # requests uses full URL. ollama python client uses 'host'. 
        self.ollama_host = OLLAMA_URL
        if not self.ollama_host.startswith("http"):
             self.ollama_host = f"http://{self.ollama_host}"
        
        try:
            self.client = ollama.Client(host=self.ollama_host)
            self._log(f"OsintAnalyzer: Skonfigurowano Ollama na {self.ollama_host}")
        except Exception as e:
            self._log(f"OsintAnalyzer: Błąd inicjalizacji klienta Ollama: {e}")

    def _log(self, msg):
        if self.logger:
            self.logger.log(msg)
        else:
            print(f"[OSINT] {msg}")

    def analyze_transcription(self, input_file, output_file, model_logic="qwen2.5:14b", model_style="qwen2.5:14b", chunk_size=12000, overlap=1000):
        if not os.path.exists(input_file):
            self._log(f"Brak pliku wejściowego: {input_file}")
            return False

        with open(input_file, 'r', encoding='utf-8') as f:
            raw = f.read()

        clean = self._clean_text(raw)
        chunks = self._create_chunks(clean, chunk_size, overlap)
        
        notes = []
        total = len(chunks)
        
        if self.progress_callback: self.progress_callback(0, "osint_analysis")

        for i, chunk in enumerate(chunks):
            if self.stop_event and self.stop_event.is_set():
                raise InterruptedError("Analiza OSINT anulowana")
            
            note = self._analyze_chunk(chunk, i, total, model_logic)
            if note:
                notes.append(note)
            
            if self.progress_callback:
                percent = (i + 1) / total * 80 # Up to 80% for analysis
                self.progress_callback(percent, "osint_analysis")

        # Combine notes
        full_notes = "\n".join(notes)
        
        # Synthesis
        if self.progress_callback: self.progress_callback(80, "osint_synthesis")
        final_md = self._synthesize_report(full_notes, model_style)
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_md)
            
        self._log(f"Raport OSINT zapisano w: {output_file}")
        if self.progress_callback: self.progress_callback(100, "osint_analysis")
        return True

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\[\d{2,3}:\d{2}\s->\s\d{2,3}:\d{2}\]', '', text) # Timestamps
        text = re.sub(r'\'', '', text) # Metadata
        return re.sub(r'\s+', ' ', text).strip()

    def _create_chunks(self, text: str, chunk_size, overlap) -> List[str]:
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        self._log(f"Tekst podzielono na {len(chunks)} fragmentów.")
        return chunks

    def _analyze_chunk(self, chunk: str, idx: int, total: int, model: str) -> str:
        prompt = f"""
        Jesteś analitykiem cyberbezpieczeństwa. Przeanalizuj ten fragment transkrypcji i wyodrębnij kluczowe informacje:
        
        1. **Narzędzia i URLe**: Wypisz nazwy narzędzi, stron i oprogramowania (wraz z kontekstem do czego służą).
        2. **Case Studies / Historie**: Streść krótko konkretne przykłady i historie opowiedziane przez prelegenta (np. wpadki AI, konkretne ataki, scamy). To jest BARDZO WAŻNE.
        3. **Techniki i Wiedza**: Jakie techniki OSINT lub manipulacji są omawiane? (np. deepfake, face swap, gaslighting).
        
        Format: Szczegółowe notatki w punktach. Zachowaj nazwy własne.
        
        FRAGMENT:
        {chunk}
        """
        self._log(f"Analiza fragmentu {idx+1}/{total}...")
        try:
            response = self.client.chat(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                options={'num_ctx': 8192}
            )
            return response['message']['content']
        except Exception as e:
            self._log(f"Błąd analizy fragmentu: {e}")
            return ""

    def _synthesize_report(self, notes: str, model: str) -> str:
        self._log("Generowanie finalnego raportu...")
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
        try:
            response = self.client.chat(
                model=model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                options={'temperature': 0.6}
            )
            return response['message']['content']
        except Exception as e:
            self._log(f"Błąd generowania raportu: {e}")
            return "Błąd generowania raportu."
