"""
backend/tts/coqui_engine.py
----------------------------
Fully Offline Text-to-Speech using Coqui TTS (VITS models).

Supports English and multilingual synthesis completely offline.
Models are downloaded once and cached locally on first run.

Install:
    pip install TTS

Usage:
    engine = CoquiTTSEngine(cfg)
    engine.load()
    wav_bytes = engine.synthesize("Hello, how can I help?", lang="en")
"""

import io
import hashlib
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("bankbot.tts.coqui")

# Map Whisper lang codes → Coqui TTS model names
# vits models are compact, fast, and fully offline after first download.
_LANG_TO_MODEL = {
    "en": "tts_models/en/ljspeech/vits",           # Fast, clear English voice
    "hi": "tts_models/hi/fairseq/vits",             # Hindi VITS (offline)
    "mr": "tts_models/multilingual/multi-dataset/your_tts",  # Multilingual fallback
}

# Default model for any language not explicitly mapped
_DEFAULT_MODEL = "tts_models/en/ljspeech/vits"


class CoquiTTSEngine:
    """Coqui TTS based fully offline TTS engine with per-language model caching."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._models: dict = {}       # lang → TTS instance
        self._cache_dir: Path = cfg.TTS_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self.available = False

    def load(self):
        """
        Load the English TTS model at startup.
        Other language models are loaded lazily on first use.
        """
        try:
            from TTS.api import TTS  # noqa: F401
        except ImportError:
            log.error("Coqui TTS not installed. Run: pip install TTS")
            print("\033[91m    [TTS] Coqui TTS not installed. Run: pip install TTS\033[0m")
            return

        try:
            print("\033[96m    [TTS] Loading Coqui English voice...\033[0m", flush=True)
            self._models["en"] = self._load_model("en")
            self.available = True
            log.info("✅ Coqui TTS loaded (English)")
            print(f"\033[92m    [TTS] Coqui TTS ready: {_LANG_TO_MODEL['en']}\033[0m")
        except Exception as e:
            log.error("Coqui TTS failed to load English model: %s", e)
            print(f"\033[91m    [TTS] Coqui load error: {e}\033[0m")

    def synthesize(self, text: str, lang: str) -> Optional[bytes]:
        """
        Convert text → WAV bytes. Fully offline.
        Falls back to English if the requested language model isn't available.

        Returns:
            WAV bytes, or None if synthesis fails.
        """
        if not self.available:
            return None

        cache_path = self._cache_path(text, lang)
        if self.cfg.TTS_ENABLE_CACHE and cache_path.exists():
            log.debug("Coqui TTS cache hit for lang=%s", lang)
            return cache_path.read_bytes()

        wav_bytes = self._render(text, lang)

        if wav_bytes and self.cfg.TTS_ENABLE_CACHE:
            try:
                cache_path.write_bytes(wav_bytes)
            except OSError as e:
                log.warning("Coqui TTS cache write failed: %s", e)

        return wav_bytes

    # ── Private ────────────────────────────────────────────────────────────

    def _load_model(self, lang: str):
        """Load and return a Coqui TTS model for the given language."""
        from TTS.api import TTS
        model_name = _LANG_TO_MODEL.get(lang, _DEFAULT_MODEL)
        log.info("Loading Coqui model: %s", model_name)
        # gpu=False → fully CPU-based, no CUDA required
        return TTS(model_name=model_name, gpu=False, progress_bar=False)

    def _render(self, text: str, lang: str) -> Optional[bytes]:
        """Render text to WAV bytes using Coqui TTS."""
        # Lazy-load model for this language
        if lang not in self._models:
            try:
                log.info("Lazy-loading Coqui model for lang=%s", lang)
                self._models[lang] = self._load_model(lang)
            except Exception as e:
                log.warning("Failed to load Coqui model for lang=%s: %s — using English", lang, e)
                lang = "en"

        tts = self._models.get(lang) or self._models.get("en")
        if not tts:
            return None

        try:
            import soundfile as sf

            # Coqui returns a list of audio samples (float32)
            samples = tts.tts(text=text)

            # Get sample rate from the model synthesizer
            sample_rate = tts.synthesizer.output_sample_rate if hasattr(tts, "synthesizer") else 22050

            # Write to in-memory WAV buffer
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format="WAV")
            wav_bytes = buf.getvalue()
            log.info("[COQUI] Synthesized %d chars in lang=%s → %d bytes WAV", len(text), lang, len(wav_bytes))
            return wav_bytes

        except Exception as e:
            log.error("Coqui TTS render error: %s", e)
            return None

    def _cache_path(self, text: str, lang: str) -> Path:
        key = hashlib.md5(f"coqui:{lang}:{text}".encode()).hexdigest()
        return self._cache_dir / f"{key}.wav"
