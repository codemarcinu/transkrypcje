from langchain_text_splitters import RecursiveCharacterTextSplitter

def smart_split_text(text: str, chunk_size: int = 6000, chunk_overlap: int = 500) -> list[str]:
    """
    Dzieli tekst na fragmenty przy użyciu RecursiveCharacterTextSplitter, dbając o semantyczną spójność.

    Ta metoda jest lepsza od prostego slice'owania, ponieważ:
    1. Rekurencyjnie próbuje dzielić tekst według listy separatorów (np. akapity -> zdania -> słowa).
    2. Gwarantuje, że chunk nie przekroczy `chunk_size` (chyba że pojedyncze słowo jest dłuższe).
    3. Zachowuje `chunk_overlap`, co jest kluczowe dla LLM, aby nie tracić kontekstu na łączeniach.
    4. Jest to standard branżowy (LangChain), bardziej przetestowany niż własne regexy.

    Args:
        text (str): Tekst wejściowy do podzielenia.
        chunk_size (int): Maksymalna długość pojedynczego fragmentu (w znakach). Domyślnie 6000.
        chunk_overlap (int): Liczba znaków nakładających się między fragmentami. Domyślnie 500.

    Returns:
        list[str]: Lista fragmentów tekstu.
    """
    if not text:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=True
    )

    return text_splitter.split_text(text)
