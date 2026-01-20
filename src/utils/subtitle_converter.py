import re
import os

def parse_vtt_timestamp(timestamp):
    # Format: HH:MM:SS.mmm or MM:SS.mmm
    parts = timestamp.replace('.', ':').split(':')
    if len(parts) == 4: # HH:MM:SS:mmm
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        milliseconds = int(parts[3])
    elif len(parts) == 3: # MM:SS:mmm (or MM:SS.mmm)
        hours = 0
        minutes = int(parts[0])
        seconds = int(parts[1])
        milliseconds = int(parts[2])
    else:
        return 0.0
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0

def format_time(seconds):
    # Converts float seconds to HH:MM:SS similar to Whisper format used in this app
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def convert_subtitle_to_txt(input_path, output_path=None):
    """
    Konwertuje plik napisów (VTT/SRT) na format tekstowy używany przez aplikację:
    [START -> END] text
    """
    if not output_path:
        base, _ = os.path.splitext(input_path)
        output_path = base + "_transkrypcja.txt"

    content = ""
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Simple parser for WebVTT/SRT logic
    # This is a basic implementation. For production robust parsing, `webvtt-py` or similar is better,
    # but we want to avoid new dependencies if possible.
    
    # Remove header
    content = re.sub(r'^WEBVTT.*\n', '', content, flags=re.MULTILINE)
    
    # Regex to find timestamp blocks and text
    # VTT/SRT patterns: 
    # 00:00:00.000 --> 00:00:05.000
    # Text line
    
    # Normalize line endings
    content = content.replace('\r\n', '\n')
    
    blocks = content.split('\n\n')
    
    with open(output_path, 'w', encoding='utf-8') as out:
        out.write(f"Język wykryty: auto (z napisów)\n")
        out.write("-" * 40 + "\n\n")
        
        for block in blocks:
            # Try to find timestamp line
            match = re.search(r'(\d{1,2}:\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[\.,]\d{3})', block)
            if match:
                start_str, end_str = match.groups()
                # Get text lines following the timestamp
                lines = block.split('\n')
                text_lines = []
                capture = False
                for line in lines:
                    if '-->' in line:
                        capture = True
                        continue
                    if capture and line.strip() and not line.strip().isdigit():
                        # Clean tags like <c> or <b>
                        clean_line = re.sub(r'<[^>]+>', '', line)
                        text_lines.append(clean_line)
                
                text = " ".join(text_lines).strip()
                if text:
                    # We keep original timestamp strings or reformat them? 
                    # App uses [00:00:00 -> 00:00:05]. VTT uses dots, SRT commas.
                    # Let's simple-replace chars to match format
                    s_clean = start_str.replace('.', ':').replace(',', ':').split('.')[0] # removing ms for simple view or keep?
                    # App format in 'transcriber.py': format_time(seconds) -> HH:MM:SS
                    
                    # Parsers:
                    # VTT: 00:00:00.000
                    # App: [00:00:00 -> 00:00:04]
                    
                    # Let's try to be consistent with app format which seems to be HH:MM:SS (no ms) based on 'format_time' in helper
                    # But verifying 'format_time' implementation in helpers.py would be good.
                    # Assuming HH:MM:SS for now.
                    
                    s_fmt = start_str.split('.')[0].split(',')[0]
                    e_fmt = end_str.split('.')[0].split(',')[0]
                    
                    out.write(f"[{s_fmt} -> {e_fmt}] {text}\n")
    
    return output_path
