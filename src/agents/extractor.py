import instructor
from openai import OpenAI
from pydantic import ValidationError
from src.core.schema import KnowledgeGraph
from src.utils.config import MODEL_EXTRACTOR, OLLAMA_URL

def extract_knowledge(chunk_text: str) -> KnowledgeGraph:
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

    system_prompt = """
    Jesteś precyzyjnym analitykiem technicznym. Twoim zadaniem jest ekstrakcja danych ze szkolenia IT/OSINT.

    ZASADY KRYTYCZNE:
    1. Output musi być CZYSTYM JSONEM zgodnym ze schematem.
    2. Nie używaj bloków kodu markdown (```json).
    3. Treść pól tekstowych (definicje, opisy) musi być w języku POLSKIM.
    4. Ignoruj sprawy organizacyjne, dygresje i żarty.
    5. Jeśli fragment nie zawiera merytoryki, zwróć puste listy.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_EXTRACTOR,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Przeanalizuj poniższy fragment i wyodrębnij wiedzę:\n\n{chunk_text}"},
            ],
            response_model=KnowledgeGraph,
            max_retries=3,
            temperature=0.1,  # Zmniejszona kreatywność dla stabilności
            extra_body={"options": {"num_ctx": 8192}}  # Wymuszenie dużego kontekstu
        )
        return response

    except ValidationError as e:
        print(f"\n[EXTRACTOR ERROR] Błąd walidacji JSON: {e}")
        return KnowledgeGraph(topics=[], tools=[], key_concepts=[], tips=[])
        
    except Exception as e:
        print(f"\n[EXTRACTOR ERROR] Błąd krytyczny LLM: {e}")
        return KnowledgeGraph(topics=[], tools=[], key_concepts=[], tips=[])
