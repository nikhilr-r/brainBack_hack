"""
scripts/download_elite_models.py
---------------------------------
Downloads high-fidelity ONNX models for the Elite TTS engine.
Approx 150MB total.
"""

import os
import urllib.request
from pathlib import Path

# URLs for high-quality VITS models
MODELS = {
    "vits-vctk-en-piper-low.onnx": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-vctk-en-piper-low.onnx",
    "vits-indic-hindi-female.onnx": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-indic-hindi-female.onnx",
    "vits-indic-marathi-female.onnx": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-indic-marathi-female.onnx",
    "tokens.txt": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/tokens.txt"
}

def download():
    base_dir = Path(__file__).parent.parent
    model_dir = base_dir / "data" / "models" / "tts"
    model_dir.mkdir(parents=True, exist_ok=True)

    print("\n🚀 Downloading Elite TTS Models (Sovereign Voice Ecosystem)...")
    print("----------------------------------------------------------")

    for name, url in MODELS.items():
        dest = model_dir / name
        if dest.exists():
            print(f"✅ Already exists: {name}")
            continue

        print(f"⏳ Downloading {name}...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
            print("Done!")
        except Exception as e:
            print(f"Error: {e}")

    print("\n✨ Elite models ready! Restart the server to enable high-fidelity voice.")

if __name__ == "__main__":
    download()
