"""
backend/tts/pyttsx_engine.py
-----------------------------
Offline Text-to-Speech using pyttsx3 + espeak-ng.

Responsibilities:
  - Initialise pyttsx3 and select Hindi/English voices
  - Render text → WAV bytes
  - Maintain a disk cache so repeated phrases are instant
  - Return raw WAV bytes (playable directly in browser via data URI)

Voice setup:
  Linux  : sudo apt install espeak-ng espeak-ng-data
  macOS  : brew install espeak
  Windows: pyttsx3 uses SAPI5 natively — no extra install needed
"""

import os
import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("bankbot.tts")


class TTSEngine:
    """pyttsx3-based offline TTS with disk caching."""

    def __init__(self, cfg):
        self.cfg         = cfg
        self._engine     = None
        self._hi_voice   = None
        self._en_voice   = None
        self._cache_dir  = cfg.TTS_CACHE_DIR

    def load(self):
        """Initialise pyttsx3 and select best available voices."""
        import pyttsx3

        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate",   self.cfg.TTS_RATE)
            self._engine.setProperty("volume", self.cfg.TTS_VOLUME)

            voices = self._engine.getProperty("voices")
            for v in voices:
                lang_raw = v.languages[0] if v.languages else ""
                if isinstance(lang_raw, bytes):
                    lang_raw = lang_raw.decode('utf-8', errors='ignore')
                lang = lang_raw.lower()
                name = v.name.lower()
                
                if "hi" in lang or "hin" in lang or "hindi" in name \
                        or "hemant" in name or "kalpana" in name:
                    if self._hi_voice is None:
                        self._hi_voice = v.id
                if ("en" in lang or "english" in name) and self._en_voice is None:
                    self._en_voice = v.id

            log.info(
                "✅ TTS ready — Hindi voice: %s | English voice: %s | %d total",
                self._hi_voice or "default",
                self._en_voice or "default",
                len(voices),
            )
        except Exception as e:
            log.warning("⚠️  pyttsx3 init issue: %s  (TTS will attempt anyway)", e)

    def synthesize(self, text: str, lang: str) -> Optional[bytes]:
        """
        Convert text to WAV audio bytes.
        Returns None on failure — caller should handle gracefully.
        Uses disk cache keyed by MD5(lang:text).
        """
        cache_path = self._cache_path(text, lang)

        # Cache hit
        if self.cfg.TTS_ENABLE_CACHE and cache_path.exists():
            log.info("TTS cache hit")
            return cache_path.read_bytes()

        # Render
        wav_bytes = self._render(text, lang)

        # Save to cache
        if wav_bytes and self.cfg.TTS_ENABLE_CACHE:
            try:
                cache_path.write_bytes(wav_bytes)
            except OSError as e:
                log.warning("TTS cache write failed: %s", e)

        return wav_bytes

    # ── Private ───────────────────────────────────────────────

    def _render(self, text: str, lang: str) -> Optional[bytes]:
        try:
            # Route non-English languages to Cloud TTS
            if lang != "en":
                import socket
                socket.setdefaulttimeout(4.0)  # Fast fail if Wi-Fi blocks Google
                try:
                    from gtts import gTTS
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        tmp = f.name
                    
                    tts = gTTS(text=text, lang=lang, slow=False)
                    tts.save(tmp)
                    
                    wav = Path(tmp).read_bytes()
                    Path(tmp).unlink(missing_ok=True)
                    return wav
                finally:
                    socket.setdefaulttimeout(None)

            if self._engine is None:
                return None
            
            # Select voice
            if self._en_voice:
                self._engine.setProperty("voice", self._en_voice)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name

            self._engine.save_to_file(text, tmp)
            self._engine.runAndWait()

            wav = Path(tmp).read_bytes()
            Path(tmp).unlink(missing_ok=True)
            return wav

        except Exception as e:
            log.error("TTS render error: %s", e)
            return None

    def _cache_path(self, text: str, lang: str) -> Path:
        key = hashlib.md5(f"{lang}:{text}".encode()).hexdigest()
        return self._cache_dir / f"{key}.wav"
