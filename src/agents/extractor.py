import instructor
from openai import OpenAI
from pydantic import ValidationError
from src.core.schema import KnowledgeGraph
from src.utils.config import MODEL_EXTRACTOR, OLLAMA_URL

def extract_knowledge(chunk_text: str, time_range: str = "Unknown", max_retries: int = 3) -> KnowledgeGraph:
    """
    Faza MAP: Zamienia tekst na ustrukturyzowane dane.
    Wymusza JSON i język polski.
    """
    
    client = instructor.from_openai(
        OpenAI(
            base_url=f"{OLLAMA_URL}/v1",
            api_key="ollama",
        ),
        mode=instructor.Mode.JSON,
    )

    system_prompt = f"""
    Jesteś precyzyjnym analitykiem technicznym. Twoim zadaniem jest ekstrakcja danych ze szkolenia IT/OSINT.
    Analizowany fragment: {time_range}

    ZASADY KRYTYCZNE:
    1. Output musi być CZYSTYM JSONEM zgodnym ze schematem.
    2. Nie używaj bloków kodu markdown (```json).
    3. Treść pól tekstowych (definicje, opisy) musi być w języku POLSKIM.
    4. Ignoruj sprawy organizacyjne, dygresje i żarty.
    5. Jeśli fragment nie zawiera merytoryki, zwróć puste listy.
    6. W polu 'time_range' wpisz dokładnie: {time_range}
    """

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_EXTRACTOR,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Przeanalizuj poniższy fragment i wyodrębnij wiedzę:\n\n{chunk_text}"},
                ],
                response_model=KnowledgeGraph,
                temperature=0.1,
                extra_body={"options": {"num_ctx": 8192}}
            )
            # Ustawiamy time_range w obiekcie, jeśli model tego nie zrobił poprawnie
            if not response.time_range:
                response.time_range = time_range
            return response

        except ValidationError as e:
            print(f"\n[EXTRACTOR] Próba {attempt+1}/{max_retries} nieudana (Błąd walidacji): {e}")
        except Exception as e:
            print(f"\n[EXTRACTOR] Próba {attempt+1}/{max_retries} nieudana (Błąd LLM): {e}")
            
    # Jeśli wszystkie próby zawiodły
    print(f"\n[EXTRACTOR CRITICAL] Pominięto fragment {time_range} po {max_retries} próbach!")
    return KnowledgeGraph(
        topics=[], 
        tools=[], 
        key_concepts=[], 
        tips=["[BŁĄD PRZETWARZANIA TEGO FRAGMENTU]"],
        time_range=time_range
    )
