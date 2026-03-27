"""
backend/stt/whisper_engine.py
------------------------------
Speech-to-Text using faster-whisper (local, fully offline).

Responsibilities:
  - Load and hold the Whisper model in memory
  - Transcribe raw audio bytes → (text, language, confidence)
  - Apply VAD filter to ignore silent/noisy segments
  - Return structured STTResult dataclass
"""

import os
import tempfile
import logging
import subprocess
import numpy as np
import soundfile as sf
from dataclasses import dataclass

log = logging.getLogger("bankbot.stt")


@dataclass
class STTResult:
    text:       str
    language:   str    # ISO code: "hi" | "en" | ...
    confidence: float  # 0.0 – 1.0  (language probability)
    success:    bool


class WhisperEngine:
    """Wraps faster-whisper for offline Hindi/English transcription."""

    def __init__(self, cfg):
        self.cfg   = cfg
        self.model = None

    def load(self):
        """Load model into memory. Call once at startup."""
        from faster_whisper import WhisperModel
        log.info("Loading Whisper (%s) on %s/%s ...",
                 self.cfg.WHISPER_MODEL, self.cfg.WHISPER_DEVICE, self.cfg.WHISPER_COMPUTE)
        self.model = WhisperModel(
            self.cfg.WHISPER_MODEL,
            device=self.cfg.WHISPER_DEVICE,
            compute_type=self.cfg.WHISPER_COMPUTE,
        )
        log.info("✅ Whisper ready")

    def transcribe(self, audio_bytes: bytes, force_language: str = "auto") -> STTResult:
        """
        Transcribe raw audio bytes (WAV or WebM).
        Returns STTResult with text, detected language, and confidence.
        """
        if self.model is None:
            raise RuntimeError("WhisperEngine not loaded. Call .load() first.")

        lang_override = self.cfg.WHISPER_LANGUAGE
        if force_language != "auto":
            lang_override = force_language

        tmp_path = None
        try:
            # Write to temp file — faster-whisper needs a file path
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            print(f"\033[90m    [STT] Audio received: {len(audio_bytes)} bytes | Language override: {lang_override}\033[0m")

            # ── Elite: Denoising ──
            if self.cfg.WHISPER_DENOISE:
                try:
                    import noisereduce as nr
                    
                    # ── Robust Audio Load ──
                    data, samplerate = None, None
                    try:
                        data, samplerate = sf.read(tmp_path)
                    except Exception:
                        # Fallback: Convert to WAV via ffmpeg
                        wav_tmp = tmp_path.replace(".webm", ".wav")
                        cmd = ["ffmpeg", "-y", "-i", tmp_path, "-ar", "16000", "-ac", "1", wav_tmp]
                        subprocess.run(cmd, capture_output=True, check=True)
                        data, samplerate = sf.read(wav_tmp)
                        if os.path.exists(wav_tmp):
                            os.unlink(wav_tmp)

                    if data is not None:
                        # Apply non-stationary noise reduction
                        reduced_noise = nr.reduce_noise(y=data, sr=samplerate, prop_decrease=0.8, stationary=False)
                        
                        # Overwrite temp file with clean audio
                        sf.write(tmp_path, reduced_noise, samplerate)
                        print(f"\033[93m    [STT] Denoising applied (Elite Mode)\033[0m")
                except Exception as de:
                    log.warning("Denoising failed: %s (Ensure ffmpeg is in PATH for WebM support)", de)

            segments, info = self.model.transcribe(
                tmp_path,
                language=lang_override,
                beam_size=self.cfg.WHISPER_BEAM,
                vad_filter=self.cfg.WHISPER_VAD,
                vad_parameters={
                    "min_silence_duration_ms": 800,
                    "speech_pad_ms": 400,
                    "threshold": 0.3,
                },
                condition_on_previous_text=False,
                initial_prompt=self.cfg.WHISPER_PROMPT,
            )

            text = " ".join(s.text for s in segments).strip()
            print(f"\033[90m    [STT] Raw transcription: '{text}'\033[0m")
            
            # Whisper Hallucination Blacklist
            HALLUCINATION_BLACKLIST = [
                "thank you", "thank you thank you", "thanks", "thanks for watching",
                "subscribe", "please subscribe", "you", "bye", "bye bye",
                "i love you", "i am done", "okay", "ok",
                "this is a", "i don't know", "i don't know anything about this",
            ]
            cl_text = text.lower().replace(".", "").replace(",", "").strip()
            if cl_text in HALLUCINATION_BLACKLIST:
                print(f"\033[91m    [STT] Blacklisted hallucination detected: '{cl_text}' -> Rejecting\033[0m")
                text = ""

            lang = info.language or "en"
            conf = float(info.language_probability)

            if not text or len(text) < 2:
                print(f"\033[91m    [STT] No usable speech detected (text='{text}', conf={conf:.2f})\033[0m")
                return STTResult(text="", language=lang, confidence=conf, success=False)

            print(f"\033[92m    [STT] ✔ Transcribed: '{text}'  lang={lang}  conf={conf:.2f}\033[0m")
            log.info("STT → '%s'  lang=%s  conf=%.2f", text[:60], lang, conf)
            return STTResult(text=text, language=lang, confidence=conf, success=True)

        except Exception as e:
            log.error("STT transcription error: %s", e)
            return STTResult(text="", language="en", confidence=0.0, success=False)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
