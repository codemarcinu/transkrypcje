import os
import json
from tqdm import tqdm
from src.utils.config import DATA_RAW, DATA_PROCESSED, DATA_OUTPUT, CHUNK_SIZE, OVERLAP, MODEL_EXTRACTOR, MODEL_WRITER, OLLAMA_URL
from src.core.text_cleaner import clean_transcript
from src.utils.text_processing import smart_split_text
from src.agents.extractor import extract_knowledge
from src.agents.writer import generate_chapter
from src.core.llm_engine import unload_model
from src.utils.validator import verify_url

def run_pipeline(input_path: str, output_dir: str = DATA_OUTPUT, topic: str = "Narzędzia OSINT, Krypto i Techniki Śledcze"):
    """
    Uruchamia pipeline generowania podręcznika.
    
    Args:
        input_path (str): Absolutna ścieżka do pliku wejściowego (transkrypcji).
        output_dir (str): Katalog zapisu wyników.
        topic (str): Temat rozdziału/podręcznika.
    """
    if not os.path.exists(input_path):
        print(f"Błąd: Nie znaleziono pliku {input_path}")
        return

    filename = os.path.basename(input_path)
    print(f"🚀 Rozpoczynam przetwarzanie: {filename}")
    print(f"📚 Temat: {topic}")

    # 1. Wczytywanie i czyszczenie
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    print("🧹 Czyszczenie tekstu...")
    clean_text = clean_transcript(raw_text)
    
    # Użycie nowego splittera
    chunks = smart_split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)
    print(f"📦 Podzielono na {len(chunks)} fragmentów (Chunk size: {CHUNK_SIZE}).")

    # 2. Mapowanie (Ekstrakcja Qwenem)
    knowledge_base = []
    print(f"\n🕵️ Ekstrakcja wiedzy (Model: {MODEL_EXTRACTOR})...")
    
    for i, chunk in enumerate(tqdm(chunks)):
        # Extract returns KnowledgeGraph object
        graph = extract_knowledge(chunk)
        
        # Walidacja URLi w narzędziach
        valid_tools = []
        for tool in graph.tools:
            if tool.url:
                if verify_url(tool.url):
                    valid_tools.append(tool)
                else:
                    print(f"\n⚠️ Wykryto halucynację URL: {tool.url} (Narzędzie: {tool.name})")
            else:
                valid_tools.append(tool)
        
        graph.tools = valid_tools
        
        # Konwersja do dict dla serializacji JSON
        knowledge_base.append(graph.model_dump())
        
        # Backup co 5 fragmentów
        if i % 5 == 0:
            with open(os.path.join(DATA_PROCESSED, "knowledge_backup.json"), 'w', encoding='utf-8') as f:
                json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

    # Zapisz pełną bazę wiedzy
    kb_path = os.path.join(DATA_PROCESSED, f"{filename}_kb.json")
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
    print(f"✅ Baza wiedzy zapisana w: {kb_path}")

    # Zwalnianie modelu Extractora przed załadowaniem Writera
    print("🧹 Zwalnianie pamięci VRAM...")
    unload_model(MODEL_EXTRACTOR)

    # 3. Redukcja (Pisanie Bielikiem)
    print(f"\n✍️ Pisanie podręcznika (Model: {MODEL_WRITER})...")
    
    final_content = f"# Podręcznik: {topic}\n\n"
    
    # Generujemy rozdział
    # Note: generate_chapter expects list of dicts, which matches knowledge_base structure now
    chapter_tools = generate_chapter(topic, knowledge_base)
    final_content += chapter_tools
    
    # Zapis
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"Podrecznik_{filename.replace('.txt', '.md')}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    print(f"\n🎉 SUKCES! Gotowy plik: {output_path}")

if __name__ == "__main__":
    # Podaj nazwę pliku, który wrzuciłeś do data/raw/
    # Domyślnie szukamy pierwszego pliku .txt w folderze raw jeśli nie podano
    files = [f for f in os.listdir(DATA_RAW) if f.endswith('.txt')]
    if files:
        TARGET_FILE = os.path.join(DATA_RAW, files[0])
        run_pipeline(TARGET_FILE)
    else:
        print("Brak plików .txt w data/raw")
