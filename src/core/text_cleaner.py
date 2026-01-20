import re

def clean_transcript(text: str) -> str:
    """Usuwa metadane, timestampy i szum z transkrypcji."""
    # 1. Usuwanie znaczników czasu [01:09 -> 01:22]
    text = re.sub(r'\[\d{2,3}:\d{2}\s->\s\d{2,3}:\d{2}\]', '', text)
    
    # 2. Usuwanie wielokrotnych spacji i pustych linii
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = ' '.join(lines)
    
    # 3. Opcjonalnie: Usuwanie powtarzalnych wtrąceń (dostosuj do speakera)
    text = re.sub(r'\s(yhh|yyy|no wiesz)\s', ' ', text, flags=re.IGNORECASE)
    
    return text

def create_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Inteligentne dzielenie tekstu bez ucinania słów."""
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunks.append(text[start:])
            break
        
        # Cofnij się do ostatniej spacji, żeby nie uciąć słowa
        last_space = text.rfind(' ', start, end)
        if last_space != -1 and last_space > start:
            end = last_space
        
        chunks.append(text[start:end])
        start = end - overlap # Zakładka
        
    return chunks
