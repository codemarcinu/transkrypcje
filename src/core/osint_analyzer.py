import os
import ollama
from src.utils.config import OLLAMA_URL, CHUNK_SIZE, OVERLAP
from src.utils.text_processing import smart_split_text

class OsintAnalyzer:
    def __init__(self, logger=None, stop_event=None, progress_callback=None):
        self.logger = logger
        self.stop_event = stop_event
        self.progress_callback = progress_callback
        
        # Obsługa adresu URL Ollamy
        host = OLLAMA_URL
        if not host.startswith("http"):
             host = f"http://{host}"
        
        try:
            self.client = ollama.Client(host=host)
            self._log(f"OsintAnalyzer: Podłączono do {host}")
        except Exception as e:
            self._log(f"OsintAnalyzer: Błąd klienta: {e}")

    def _log(self, msg):
        if self.logger:
            self.logger.log(msg)
        else:
            print(f"[OSINT] {msg}")

    def analyze_transcription(self, input_file, output_file, model_name="bielik"): # Domyślnie Bielik
        if not os.path.exists(input_file):
            self._log(f"Brak pliku: {input_file}")
            return False

        self._log(f"Wczytywanie: {input_file}")
        
        # 1. Wczytanie tekstu (Leniwe czytanie byłoby lepsze, ale dla smart_split potrzebujemy całości w RAM na chwilę)
        # Przy plikach tekstowych <100MB to nie problem.
        with open(input_file, 'r', encoding='utf-8') as f:
            full_text = f.read()

        # 2. Inteligentny podział
        chunks = smart_split_text(full_text, max_length=CHUNK_SIZE, overlap=OVERLAP)
        total_chunks = len(chunks)
        self._log(f"Podział na {total_chunks} fragmentów semantycznych.")

        extracted_notes = []
        
        # 3. ETAP MAP (Analiza fragmentów)
        for i, chunk in enumerate(chunks):
            if self.stop_event and self.stop_event.is_set():
                raise InterruptedError("Analiza przerwana")
            
            # Kontekstowy nagłówek dla modelu
            chunk_context = f"[FRAGMENT {i+1}/{total_chunks}]"
            note = self._analyze_chunk_stream(chunk, chunk_context, model_name)
            
            if note:
                extracted_notes.append(note)
            
            if self.progress_callback:
                # 0-70% postępu to analiza fragmentów
                prog = (i + 1) / total_chunks * 70
                self.progress_callback(prog, "osint_analysis")

        # 4. ETAP REDUCE (Synteza)
        self._log("Synteza raportu końcowego...")
        full_notes_text = "\n\n---\n\n".join(extracted_notes)
        
        # Jeśli notatki są za długie, trzeba je skrócić przed finałem (Intermediate Reduce)
        if len(full_notes_text) > 12000:
             self._log("Notatki zbyt obszerne, wykonuję kondensację...")
             full_notes_text = self._condense_notes(full_notes_text, model_name)

        final_report = self._generate_final_report(full_notes_text, model_name)

        # 5. Zapis
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_report)
            
        self._log(f"Gotowe. Raport: {output_file}")
        if self.progress_callback: self.progress_callback(100, "finished")
        return True

    def _analyze_chunk_stream(self, text, context_header, model):
        """Używa streamingu, aby móc przerwać w trakcie generowania"""
        prompt = f"""
        {context_header}
        Przeanalizuj ten fragment transkrypcji pod kątem cyberbezpieczeństwa i OSINT.
        Wypisz TYLKO konkretne dane w formacie listy:
        - NARZĘDZIA: (nazwy softu, skryptów)
        - URL/DOMENY: (adresy www, IP)
        - ZAGROŻENIA/ATAKI: (omawiane metody, wektory ataku)
        - CIEKAWOSTKI: (kontekst, nazwiska, firmy)
        
        Jeśli fragment nie zawiera takich danych, napisz "BRAK DANYCH".
        Nie streszczaj rozmowy, wyciągaj "mięso".
        
        TEKST:
        {text}
        """
        
        response_content = ""
        try:
            stream = self.client.chat(
                model=model,
                messages=[
                    {'role': 'system', 'content': 'Jesteś precyzyjnym analitykiem OSINT. Odpowiadasz zwięźle.'},
                    {'role': 'user', 'content': prompt}
                ],
                stream=True,
                options={'num_ctx': 8192, 'temperature': 0.2} # Niska temperatura dla faktów
            )
            
            for chunk in stream:
                if self.stop_event and self.stop_event.is_set():
                    self._log("Przerwano generowanie przez użytkownika.")
                    return None
                
                content = chunk['message']['content']
                response_content += content
                # Opcjonalnie: print(content, end='', flush=True) dla debugu w konsoli
                
            return response_content.strip()

        except Exception as e:
            self._log(f"Błąd LLM: {e}")
            return None

    def _condense_notes(self, notes, model):
        """Kondensacja notatek, jeśli przekraczają okno kontekstowe"""
        prompt = f"""
        Poniżej znajdują się surowe notatki z analizy transkrypcji.
        Scal je, usuń duplikaty i sformatuj jako spójną listę znalezisk OSINT.
        
        NOTATKI:
        {notes[:16000]} 
        """ 
        # Hard limit znaków dla kondensacji, Bielik powinien to udźwignąć
        
        response = self.client.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False,
            options={'num_ctx': 8192} 
        )
        return response['message']['content']

    def _generate_final_report(self, notes, model):
        system_prompt = """
        Jesteś Senior Analitykiem Cybersec. Piszesz raport w języku polskim.
        Twój styl jest: konkretny, techniczny, bez lania wody.
        """
        
        user_prompt = f"""
        Na podstawie poniższych notatek stwórz profesjonalny RAPORT OSINT/CYBERSEC.
        
        STRUKTURA:
        1. **Executive Summary**: 3 zdania o czym był materiał.
        2. **Case Studies**: Opis konkretnych historii/ataków (kto, jak, skutki).
        3. **Narzędziownik**: Tabela lub lista narzędzi z opisem zastosowania.
        4. **IoC / Ślady**: URLe, Domeny, IP (jeśli znaleziono).
        5. **Wnioski i Rekomendacje**.
        
        DANE WEJŚCIOWE:
        {notes}
        """
        
        response = self.client.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=False,
            options={'num_ctx': 8192, 'temperature': 0.4}
        )
        return response['message']['content']
