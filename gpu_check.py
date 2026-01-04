import torch
import os
import sys
from faster_whisper import WhisperModel

print(f"Python: {sys.version}")
print(f"PyTorch: {torch.__version__}")
try:
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Version: {torch.version.cuda}")
except Exception as e:
    print(f"Error checking CUDA: {e}")

print("-" * 20)
print("Checking Whisper Model Path...")
# Try to instantiate a tiny model to see where it goes (or check dry run if possible, but instantiation is surest)
# We won't actually transcribe to save time, just load.
try:
    # Use a custom path to be sure
    cache_dir = os.path.join(os.getcwd(), "models")
    print(f"Proposed Cache Dir: {cache_dir}")
    
    # Check default behavior first (where it looks)
    # faster-whisper default uses standard HF cache if download_root is None
    print("Attempting to load 'tiny' model with default settings...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8", download_root=cache_dir)
    print("Model loaded successfully.")
    
    # List files in cache dir to verify
    if os.path.exists(cache_dir):
        print(f"Files in {cache_dir}:")
        for root, dirs, files in os.walk(cache_dir):
            for file in files:
                print(os.path.join(root, file))
    else:
        print("Cache dir not created.")

except Exception as e:
    print(f"Error loading model: {e}")
