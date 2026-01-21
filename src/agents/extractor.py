import time
import re
from typing import Optional
from src.core.llm_engine import LLMEngine
from src.core.schema import KnowledgeGraph

class KnowledgeExtractor:
    def __init__(self):
        self.llm = LLMEngine(model_type="extractor")

    def _extract_timestamp(self, text: str) -> Optional[str]:
        """
        Wyciąga czas w formacie MM:SS lub H:MM:SS z początku tekstu.
        Obsługuje formaty: [01:04], [01:04 -> 01:08], (01:04).
        """
        # Szuka wzorca czasu na początku ciągu lub po nowej linii
        match = re.search(r'(?:^|\n)[\[\(](\d{1,2}:\d{2}(?::\d{2})?)', text)
        if match:
            return match.group(1)
        return None

    def extract_knowledge(self, chunk_text: str, chunk_id: str | int = 0) -> KnowledgeGraph:
        """
        Ekstrakcja wiedzy z fragmentu tekstu z mechanizmem Retry i Regex.
        """
        
        # 1. Determinisyczne wyciąganie czasu (zamiast LLM)
        real_timestamp = self._extract_timestamp(chunk_text)
        # Fallback: Jeśli nie ma czasu w tekście, użyj ID fragmentu
        final_time_marker = real_timestamp if real_timestamp else f"{chunk_id}"

        system_prompt = """
        Jesteś analitykiem cyberbezpieczeństwa. Twoim zadaniem jest strukturyzacja wiedzy z transkrypcji.
        
        ZASADY:
        1. Narzędzia: Wymień tylko konkretne oprogramowanie/sprzęt.
        2. Pojęcia: Definiuj trudne terminy (żargon, akronimy).
        3. Porady: Wyciągnij praktyczne "Tip of the day".
        4. Bądź zwięzły. Jeśli kategoria jest pusta, zostaw ją pustą.
        """

        user_prompt = f"Przeanalizuj poniższy fragment i wyekstrahuj wiedzę:\n\n{chunk_text}"

        # 2. Pętla Retry (odporność na błędy API/Modelu)
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # Wywołanie modelu
                response: KnowledgeGraph = self.llm.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=KnowledgeGraph
                )
                
                # Nadpisanie czasu wartością z Regexa (gwarancja poprawności)
                response.time_range = final_time_marker
                return response

            except Exception as e:
                last_error = e
                print(f"[EXTRACTOR] Błąd przetwarzania (próba {attempt + 1}/{max_retries}): {e}")
                time.sleep(1) # Odczekaj chwilę

        # 3. Failover - Zwrócenie pustego obiektu z błędem zamiast wysypania programu
        print(f"[EXTRACTOR CRITICAL] Pominięto fragment {chunk_id} po {max_retries} próbach.")
        return KnowledgeGraph(
            topics=[], 
            tools=[], 
            key_concepts=[], 
            tips=[f"BŁĄD PRZETWARZANIA: {str(last_error)}"],
            time_range=final_time_marker
        )

# Wrapper dla zachowania kompatybilności wstecznej
def extract_knowledge(chunk_text: str, time_range: str | int = 0) -> KnowledgeGraph:
    extractor = KnowledgeExtractor()
    return extractor.extract_knowledge(chunk_text, chunk_id=time_range)
