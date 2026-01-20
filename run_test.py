
import os
import sys
from src.core.osint_analyzer import OsintAnalyzer
from src.utils.config import DEFAULT_OLLAMA_MODEL

# Setup logger mock
class MockLogger:
    def log(self, msg):
        print(f"[LOG] {msg}")

def main():
    input_file = "/home/marcin/transkrypcje/Narzędziownik OSINT 2.0 Reloaded - sesja 6_transkrypcja.txt"
    output_file = "/home/marcin/transkrypcje/RAPORT_TEST.md"
    
    if not os.path.exists(input_file):
        print(f"Error: Input file not found at {input_file}")
        # Try finding it in current dir if path is slightly off
        input_file = "Narzędziownik OSINT 2.0 Reloaded - sesja 6_transkrypcja.txt"
        if not os.path.exists(input_file):
            print("Error: Input file not found in current directory either.")
            sys.exit(1)

    print(f"Starting analysis on: {input_file}")
    print(f"Using model: {DEFAULT_OLLAMA_MODEL}")
    
    analyzer = OsintAnalyzer(logger=MockLogger())
    
    try:
        success = analyzer.analyze_transcription(input_file, output_file, model_name=DEFAULT_OLLAMA_MODEL)
        if success:
            print(f"Analysis complete! Output saved to: {output_file}")
        else:
            print("Analysis failed.")
    except Exception as e:
        print(f"Exception during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
