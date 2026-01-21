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
