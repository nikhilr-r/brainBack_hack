"""
backend/tts/elite_engine.py
----------------------------
Elite Offline Text-to-Speech using Sherpa-ONNX (VITS).
Provides high-fidelity, human-like voices for Hindi, Marathi, and English.

This engine is significantly higher quality than pyttsx3.
"""

import os
import hashlib
import logging
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Optional

log = logging.getLogger("bankbot.tts.elite")


class EliteTTSEngine:
    """Sherpa-ONNX based high-fidelity offline TTS."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._models = {}
        self._cache_dir = cfg.TTS_CACHE_DIR
        self._cache_dir.mkdir(exist_ok=True)

    def load(self):
        """
        Load Sherpa-ONNX models from subfolder structure.
        Each entry in cfg.TTS_MODELS maps a lang code -> folder name.
        Inside each folder: one .onnx file + tokens.txt
        Download with: py scripts/download_elite_models.py
        """
        try:
            import sherpa_onnx
            
            model_dir = self.cfg.TTS_MODEL_DIR

            for lang, folder_name in self.cfg.TTS_MODELS.items():
                folder_path = model_dir / folder_name
                if not folder_path.exists():
                    log.debug("Elite TTS folder missing for %s: %s — skipping", lang, folder_path)
                    continue

                # Find the .onnx file inside the folder (there should be exactly one)
                onnx_files = list(folder_path.glob("*.onnx"))
                if not onnx_files:
                    log.debug("No .onnx file found in %s — skipping", folder_path)
                    continue
                model_path = onnx_files[0]  # use the first one

                # Find tokens.txt inside the folder
                tokens_path = folder_path / self.cfg.TTS_TOKENS
                if not tokens_path.exists():
                    log.debug("tokens.txt not found in %s — skipping", folder_path)
                    continue

                # Configure VITS model
                try:
                    vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=str(model_path),
                        tokens=str(tokens_path),
                        data_dir="",
                        noise_scale=0.667,
                        noise_scale_w=0.8,
                        length_scale=1.0,
                    )
                    
                    tts_config = sherpa_onnx.OfflineTtsModelConfig(
                        vits=vits_config,
                        num_threads=2,
                        debug=False,
                        provider="cpu",
                    )
                    
                    self._models[lang] = sherpa_onnx.OfflineTts(tts_config)
                    log.info("✅ Elite TTS Loaded: %s (%s)", lang, model_path.name)
                    print(f"\033[92m    [TTS] Loaded Elite voice for '{lang}': {model_path.name}\033[0m")
                except Exception as load_err:
                    log.warning("Failed to load Elite TTS for %s: %s", lang, load_err)

        except ImportError:
            log.warning("sherpa-onnx not installed — Elite TTS unavailable. pip install sherpa-onnx")
        except Exception as e:
            log.error("Elite TTS load error: %s", e)

    def synthesize(self, text: str, lang: str) -> Optional[bytes]:
        """
        Convert text to WAV audio bytes using a high-quality model.
        Falls back to cache if available.
        """
        cache_path = self._cache_path(text, lang)

        # Cache hit
        if self.cfg.TTS_ENABLE_CACHE and cache_path.exists():
            log.info("Elite TTS cache hit")
            return cache_path.read_bytes()

        # Render
        wav_bytes = self._render(text, lang)

        # Save to cache
        if wav_bytes and self.cfg.TTS_ENABLE_CACHE:
            try:
                cache_path.write_bytes(wav_bytes)
            except OSError as e:
                log.warning("Elite TTS cache write failed: %s", e)

        return wav_bytes

    def _render(self, text: str, lang: str) -> Optional[bytes]:
        """Actual rendering via Sherpa-ONNX."""
        tts = self._models.get(lang)
        if not tts:
            # Fallback to English if target lang not loaded
            tts = self._models.get("en")
        
        if not tts:
            log.warning("No Elite TTS models available for %s", lang)
            return None

        try:
            import io
            # Generate audio data (numpy array)
            audio = tts.generate(text)
            
            # Convert to WAV bytes in-memory
            with io.BytesIO() as buf:
                sf.write(buf, audio.samples, audio.sample_rate, format='WAV')
                return buf.getvalue()

        except Exception as e:
            log.error("Elite TTS render error: %s", e)
            return None

    def _cache_path(self, text: str, lang: str) -> Path:
        key = hashlib.md5(f"elite:{lang}:{text}".encode()).hexdigest()
        return self._cache_dir / f"{key}.wav"
