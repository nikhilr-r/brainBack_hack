"""
scripts/download_elite_models.py
---------------------------------
Downloads high-fidelity ONNX models for the Elite TTS engine (Sherpa-ONNX VITS).

Models are downloaded as .tar.bz2 archives and extracted into data/models/tts/.
Each model has its own sub-folder containing the .onnx model and tokens.txt.

Approx download sizes:
  - vits-piper-en_US-amy-low  : ~22 MB (English)
  - vits-piper-hi-0-madmom-low: ~22 MB (Hindi)

Usage:
    py scripts/download_elite_models.py
"""

import tarfile
import urllib.request
import shutil
from pathlib import Path

# ── Real verified URLs from k2-fsa/sherpa-onnx GitHub releases ──────────────
# These are .tar.bz2 archives. Each extracts to a folder like vits-piper-en_US-amy-low/
MODELS = [
    {
        "name": "vits-piper-en_US-amy-low",    # English
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-amy-low.tar.bz2",
        "lang": "en",
    },
    {
        "name": "vits-piper-hi-0-madmom-low",   # Hindi
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-hi-0-madmom-low.tar.bz2",
        "lang": "hi",
    },
]

def download():
    base_dir = Path(__file__).parent.parent
    model_dir = base_dir / "data" / "models" / "tts"
    model_dir.mkdir(parents=True, exist_ok=True)

    print("\n🚀 Downloading Elite TTS Models (Sherpa-ONNX VITS Piper)...")
    print("──────────────────────────────────────────────────────────")

    downloaded_any = False

    for m in MODELS:
        name     = m["name"]
        url      = m["url"]
        dest_dir = model_dir / name

        if dest_dir.exists() and any(dest_dir.glob("*.onnx")):
            print(f"  ✅ Already present: {name}")
            downloaded_any = True
            continue

        archive_path = model_dir / f"{name}.tar.bz2"
        print(f"  ⏳ Downloading {name}  (~22 MB)...", end=" ", flush=True)

        try:
            # Stream download with progress
            def reporthook(block_num, block_size, total_size):
                mb_done = block_num * block_size / 1_048_576
                if block_num % 100 == 0:
                    print(f"\r  ⏳ Downloading {name}... {mb_done:.1f} MB", end="", flush=True)

            urllib.request.urlretrieve(url, archive_path, reporthook=reporthook)
            print(f"\r  📦 Extracting {name}...              ", end=" ", flush=True)

            with tarfile.open(archive_path, "r:bz2") as tar:
                tar.extractall(model_dir)
            
            archive_path.unlink()  # delete the archive after extraction
            print("✅ Done!")
            downloaded_any = True

        except Exception as e:
            print(f"\n  ❌ Failed: {e}")
            print(f"     URL: {url}")
            if archive_path.exists():
                archive_path.unlink()

    if downloaded_any:
        print("\n  ✨ Elite TTS models ready!")
        print("  → Restart the server to enable high-fidelity voice responses.\n")
    else:
        print("\n  ⚠️  No models were downloaded. Check your internet connection.")
        print("  The server will use pyttsx3 as fallback.\n")


if __name__ == "__main__":
    download()
