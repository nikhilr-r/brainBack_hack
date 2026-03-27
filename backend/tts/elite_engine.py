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
        Load Sherpa-ONNX models for the configured languages.
        Models must be downloaded using scripts/download_elite_models.py first.
        """
        try:
            import sherpa_onnx
            
            model_dir = self.cfg.TTS_MODEL_DIR
            if not model_dir.exists():
                log.warning("Elite TTS models not found at %s. Run scripts/download_elite_models.py", model_dir)
                return

            tokens = str(model_dir / self.cfg.TTS_TOKENS)

            for lang, model_name in self.cfg.TTS_MODELS.items():
                model_path = model_dir / model_name
                if not model_path.exists():
                    log.warning("Elite TTS model for %s missing: %s", lang, model_name)
                    continue

                # Configure VITS model
                vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(model_path),
                    tokens=tokens,
                    data_dir="",
                    noise_scale=0.667,
                    noise_scale_w=0.8,
                    length_scale=1.0,
                )
                
                tts_config = sherpa_onnx.OfflineTtsModelConfig(
                    vits=vits_config,
                    num_threads=1,
                    debug=False,
                    provider="cpu",
                )
                
                self._models[lang] = sherpa_onnx.OfflineTts(tts_config)
                log.info("✅ Elite TTS Loaded: %s", lang)

        except ImportError:
            log.error("Sherpa-ONNX not installed. Run: pip install sherpa-onnx")
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
