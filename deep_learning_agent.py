import os
print("DEBUG: Import os")
import re
import time
import json
import argparse
import sys
print("DEBUG: Imports done")
from typing import List
import ollama
print("DEBUG: Ollama imported")

# --- DOMYŚLNA KONFIGURACJA ---
DEFAULT_CONFIG = {
    "input_file": "Narzędziownik OSINT 2.0 Reloaded - sesja 6_transkrypcja.txt",
    "output_file": "PODRECZNIK_OSINT_FULL.md",
    "checkpoint_file": "temp_facts_checkpoint.json",
    "model_extractor": "qwen2.5:14b",   # Logika/Ekstrakcja
    "model_writer": "SpeakLeash/bielik-11b-v3.0-instruct:Q5_K_M",    # Styl/Pisanie
    "chunk_size": 10000,                # Duże kawałki dla kontekstu
    "overlap": 500,
    "host": "http://localhost:11434"
}

class DeepCourseAgent:
    def __init__(self, config: dict):
        print("DEBUG: Agent init start")
        self.config = config
        self.client = ollama.Client(host=config["host"])
        print("DEBUG: Agent init done")

    def log(self, msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def _clean_text(self, text: str) -> str:
        self.log("Czyszczenie transkrypcji...")
        text = re.sub(r'\[\d{2,3}:\d{2}\s->\s\d{2,3}:\d{2}\]', '', text)
        text = re.sub(r"'", '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _create_chunks(self, text: str) -> List[str]:
        chunks = []
        start = 0
        text_len = len(text)
        self.log(f"Length of text: {text_len}")
        while start < text_len:
            end = start + self.config["chunk_size"]
            # Szukanie kropki, by nie ciąć w połowie zdania
            search_end = min(end + 200, text_len)
            last_period = text.rfind('.', start, search_end)
            
            if last_period != -1 and last_period > start + (self.config["chunk_size"] * 0.8):
                end = last_period + 1
            
            chunks.append(text[start:end])
            start = end - self.config["overlap"]
            if start >= text_len: break # Zabezpieczenie pętli
            
        self.log(f"Podzielono tekst na {len(chunks)} segmentów.")
        return chunks

    def _phase_1_extraction(self, chunks: List[str]) -> List[str]:
        """Faza 1: Ekstrakcja faktów (Qwen)."""
        self.log(f"--- FAZA 1: EKSTRAKCJA ({self.config['model_extractor']}) ---")
        facts = []
        
        # Pre-warm modelu
        try:
            self.log("Pinging ollama...")
            self.client.chat(model=self.config["model_extractor"], messages=[{'role':'user','content':'ping'}])
            self.log("Ping successful")
        except Exception as e:
            self.log(f"BŁĄD: Nie można połączyć z modelem {self.config['model_extractor']}. Sprawdź 'ollama list'. Error: {e}")
            sys.exit(1)

        total = len(chunks)
        for i, chunk in enumerate(chunks):
            self.log(f"Analiza techniczna: {i+1}/{total}")
            prompt = f"""
            Działasz jako inżynier danych. Przeanalizuj fragment transkrypcji szkolenia IT.
            Wypisz SUROWE DANE techniczne:
            - Nazwy narzędzi, linki, komendy.
            - Kroki techniczne (step-by-step).
            - Definicje i pojęcia.
            
            Ignoruj: dygresje, żarty, kwestie organizacyjne.
            Wyjście: Tylko lista faktów.
            
            FRAGMENT:
            {chunk}
            """
            try:
                response = self.client.chat(
                    model=self.config["model_extractor"],
                    messages=[{'role': 'user', 'content': prompt}],
                    options={'num_ctx': 8192, 'temperature': 0.2}
                )
                facts.append(response['message']['content'])
            except Exception as e:
                self.log(f"Błąd przy fragmencie {i+1}: {e}")
                facts.append(f"[BŁĄD ANALIZY FRAGMENTU {i+1}]")

        # Zapis checkpointu
        with open(self.config["checkpoint_file"], "w", encoding="utf-8") as f:
            json.dump(facts, f, ensure_ascii=False, indent=2)
        self.log(f"Checkpoint zapisany: {self.config['checkpoint_file']}")
        
        return facts

    def _phase_2_writing(self, facts_list: List[str]):
        """Faza 2: Pisanie podręcznika (Bielik)."""
        self.log(f"--- FAZA 2: PISANIE ({self.config['model_writer']}) ---")
        self.log("Ładowanie modelu pisarza (wymuszenie VRAM swap)...")
        
        try:
            self.client.chat(model=self.config["model_writer"], messages=[{'role':'user','content':'start'}])
        except Exception as e:
            self.log(f"BŁĄD: Nie można załadować modelu {self.config['model_writer']}.")
            sys.exit(1)

        # Inicjalizacja pliku (jeśli nie istnieje, stwórz nagłówek)
        if not os.path.exists(self.config["output_file"]):
            with open(self.config["output_file"], "w", encoding="utf-8") as f:
                f.write("# KOMPLEKSOWY PODRĘCZNIK OSINT\n\n_Wygenerowano przez AI Agent_\n\n")

        total = len(facts_list)
        for i, facts in enumerate(facts_list):
            self.log(f"Pisanie Rozdziału {i+1}/{total}...")
            
            prompt = f"""
            Jesteś autorem specjalistycznych książek IT. 
            Twoim zadaniem jest napisanie rozdziału podręcznika na podstawie dostarczonych notatek.
            
            WYMAGANIA:
            1. Objętość: Bądź wylewny. Tłumacz wszystko dokładnie.
            2. Struktura: Używaj nagłówków H3 (###), list i bloków kodu.
            3. Język: Profesjonalny polski, styl akademicki/inżynierski.
            4. Treść: Nie wspominaj, że "tekst mówi o...", po prostu przekaż wiedzę.
            
            NOTATKI DO ROZDZIAŁU:
            {facts}
            """
            
            try:
                response = self.client.chat(
                    model=self.config["model_writer"],
                    messages=[{'role': 'user', 'content': prompt}],
                    options={'num_ctx': 8192, 'temperature': 0.6}
                )
                
                content = response['message']['content']
                
                # Append mode - bezpieczny zapis
                with open(self.config["output_file"], "a", encoding="utf-8") as f:
                    f.write(f"\n## ROZDZIAŁ {i+1}\n\n{content}\n\n---\n")
                    
            except Exception as e:
                self.log(f"Błąd przy pisaniu rozdziału {i+1}: {e}")

    def run(self, force_resume=False):
        print("DEBUG: Run started", flush=True)
        start_time = time.time()
        facts = []

        # LOGIKA RESUME: Sprawdź czy istnieje checkpoint
        print(f"DEBUG: Checking checkpoint {self.config['checkpoint_file']}")
        if os.path.exists(self.config["checkpoint_file"]):
            if force_resume:
                self.log(f"Wymuszono wznowienie. Wczytywanie: {self.config['checkpoint_file']}")
                with open(self.config["checkpoint_file"], 'r', encoding='utf-8') as f:
                    facts = json.load(f)
            else:
                self.log("WARNING: Checkpoint exists but input disabled in debug mode - assuming NO RESUME for now unless forced")
                # skipping input for debug
                pass

        # Jeśli facts puste (nie wznowiono lub brak checkpointu), uruchom Fazę 1
        if not facts:
            print(f"DEBUG: Reading input {self.config['input_file']}")
            if not os.path.exists(self.config["input_file"]):
                self.log(f"BŁĄD: Brak pliku {self.config['input_file']}")
                return
            
            with open(self.config["input_file"], 'r', encoding='utf-8') as f:
                raw_text = f.read()
            print("DEBUG: Read file done")
                
            clean_text = self._clean_text(raw_text)
            chunks = self._create_chunks(clean_text)
            facts = self._phase_1_extraction(chunks)

        # Uruchom Fazę 2
        self._phase_2_writing(facts)
        
        duration = (time.time() - start_time) / 60
        self.log(f"ZAKOŃCZONO. Czas: {duration:.2f} min. Plik: {self.config['output_file']}")

if __name__ == "__main__":
    print("DEBUG: main block start")
    parser = argparse.ArgumentParser(description="Agent AI do generowania podręczników z transkrypcji.")
    parser.add_argument("--resume", action="store_true", help="Automatycznie wznów z checkpointu jeśli istnieje")
    parser.add_argument("--input", type=str, help="Ścieżka do pliku wejściowego")
    args = parser.parse_args()
    print(f"DEBUG: args parsed: {args}")

    if args.input:
        DEFAULT_CONFIG["input_file"] = args.input

    agent = DeepCourseAgent(DEFAULT_CONFIG)
    agent.run(force_resume=args.resume)
