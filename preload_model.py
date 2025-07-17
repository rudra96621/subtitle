# preload_model.py
import whisper
import os

# Make sure it's cached in the same location
os.environ["WHISPER_CACHE_DIR"] = os.path.expanduser("~/.cache/whisper")
whisper.load_model("medium")  # Or 'tiny', 'large', etc.
print("✅ Model preloaded and cached.")
