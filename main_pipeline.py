import os
import json
from tqdm import tqdm
from src.utils.config import DATA_RAW, DATA_PROCESSED, DATA_OUTPUT, CHUNK_SIZE, OVERLAP
from src.core.text_cleaner import clean_transcript, create_chunks
from src.agents.extractor import extract_knowledge
from src.agents.writer import generate_chapter

def run_pipeline(filename: str):
    input_path = os.path.join(DATA_RAW, filename)
    if not os.path.exists(input_path):
        print(f"Błąd: Nie znaleziono pliku {input_path}")
        return

    print(f"🚀 Rozpoczynam przetwarzanie: {filename}")

    # 1. Wczytywanie i czyszczenie
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    print("🧹 Czyszczenie tekstu...")
    clean_text = clean_transcript(raw_text)
    chunks = create_chunks(clean_text, CHUNK_SIZE, OVERLAP)
    print(f"📦 Podzielono na {len(chunks)} fragmentów (Chunk size: {CHUNK_SIZE}).")

    # 2. Mapowanie (Ekstrakcja Qwenem)
    knowledge_base = []
    print("\n🕵️ Ekstrakcja wiedzy (Model: Qwen 2.5 14B)...")
    
    for i, chunk in enumerate(tqdm(chunks)):
        data = extract_knowledge(chunk)
        if data:
            knowledge_base.append(data)
        
        # Backup co 5 fragmentów
        if i % 5 == 0:
            with open(os.path.join(DATA_PROCESSED, "knowledge_backup.json"), 'w', encoding='utf-8') as f:
                json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

    # Zapisz pełną bazę wiedzy
    kb_path = os.path.join(DATA_PROCESSED, f"{filename}_kb.json")
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
    print(f"✅ Baza wiedzy zapisana w: {kb_path}")

    # 3. Redukcja (Pisanie Bielikiem)
    print("\n✍️ Pisanie podręcznika (Model: Bielik 11B)...")
    
    # Tu upraszczamy - wrzucamy wszystko do jednego worka. 
    # W wersji 2.0 można by tu dodać klastrowanie tematów.
    
    final_content = "# Podręcznik Szkoleniowy (Wygenerowany przez AI)\n\n"
    
    # Generujemy rozdział "Narzędzia i Techniki"
    chapter_tools = generate_chapter("Narzędzia OSINT, Krypto i Techniki Śledcze", knowledge_base)
    final_content += chapter_tools
    
    # Zapis
    output_path = os.path.join(DATA_OUTPUT, f"Podrecznik_{filename.replace('.txt', '.md')}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    print(f"\n🎉 SUKCES! Gotowy plik: {output_path}")

if __name__ == "__main__":
    # Podaj nazwę pliku, który wrzuciłeś do data/raw/
    TARGET_FILE = "Narzędziownik OSINT 2.0 Reloaded - sesja 6_transkrypcja.txt"
    run_pipeline(TARGET_FILE)
