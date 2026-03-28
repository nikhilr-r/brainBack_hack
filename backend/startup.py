"""
backend/startup.py
------------------
Startup sequence — loads all models in the correct order
and validates the system before accepting requests.

Prints a clear status table so the team can see what's working
at a glance before the demo.
"""

import logging
import sys

log = logging.getLogger("bankbot.startup")


def run_startup_checks(cfg) -> None:
    """
    Load all models and attach them to cfg as runtime singletons.
    Exits with a clear error message if any critical component fails.
    """
    from backend.stt     import WhisperEngine
    from backend.rag     import Embedder, Retriever
    from backend.llm     import OllamaClient
    from backend.tts     import TTSEngine, EliteTTSEngine
    from backend.session import SessionManager
    from backend.pipeline import VoicePipeline
    from config.knowledge_base import BANK_KNOWLEDGE

    errors = []

    # ── 1. STT ────────────────────────────────────────────────
    print("  [1/5] Loading Whisper STT...", end=" ", flush=True)
    stt = WhisperEngine(cfg)
    try:
        stt.load()
        print("✅")
    except Exception as e:
        print("❌")
        errors.append(f"STT: {e}\n       → pip install faster-whisper")

    # ── 2. Embedder ───────────────────────────────────────────
    print("  [2/5] Loading sentence embedder...", end=" ", flush=True)
    embedder = Embedder(cfg.EMBED_MODEL)
    try:
        embedder.load()
        print("✅")
    except Exception as e:
        print("❌")
        errors.append(f"Embedder: {e}\n       → pip install sentence-transformers")

    # ── 3. Knowledge base ─────────────────────────────────────
    print("  [3/5] Building knowledge base...", end=" ", flush=True)
    retriever = Retriever(cfg, embedder)
    try:
        retriever.build(BANK_KNOWLEDGE)
        print(f"✅  ({len(BANK_KNOWLEDGE)} entries)")
    except Exception as e:
        print("❌")
        errors.append(f"RAG: {e}\n       → pip install chromadb")

    # ── 4. TTS ────────────────────────────────────────────────
    print("  [4/5] Initialising TTS...", end=" ", flush=True)
    tts = None
    if cfg.TTS_ENGINE == "elite":
        elite = EliteTTSEngine(cfg)
        try:
            elite.load()
        except Exception:
            pass
        
        if elite._models:
            # At least one language model loaded ✅
            tts = elite
            engine_name = f"Sherpa-ONNX Elite ({list(elite._models.keys())})"
        else:
            # No models downloaded → fallback silently to pyttsx3
            print("\n  [4/5] ⚠️  Elite TTS models not found → falling back to pyttsx3", flush=True)
            print("         └─ Run: py scripts/download_elite_models.py  (to get HD voices)", flush=True)
            print("  [4/5]", end=" ", flush=True)
            tts = TTSEngine(cfg)
            engine_name = "pyttsx3 (Fallback)"
    else:
        tts = TTSEngine(cfg)
        engine_name = "pyttsx3 (Basic)"

    try:
        if not hasattr(tts, "_models"):  # basic TTSEngine needs load()
            tts.load()
        print(f"✅  ({engine_name})")
    except Exception as e:
        print(f"⚠️   ({e})")   # TTS failure is non-fatal

    # ── 5. Ollama LLM ─────────────────────────────────────────
    print("  [5/5] Connecting to Ollama...", end=" ", flush=True)
    llm = OllamaClient(cfg)
    model = llm.detect_model()
    if model:
        print(f"✅  ({model})")
    else:
        print("⚠️   model not found")
        print()
        print("  ┌─────────────────────────────────────────────────┐")
        print("  │  To fix: open a new terminal and run:           │")
        print("  │    ollama serve                                 │")
        print("  │    ollama pull phi3:mini                        │")
        print("  └─────────────────────────────────────────────────┘")

    # ── Abort on critical errors ──────────────────────────────
    if errors:
        print()
        print("  ❌ Critical startup errors:")
        for e in errors:
            print(f"     • {e}")
        sys.exit(1)

    # ── Build session manager + pipeline ─────────────────────
    sessions = SessionManager(timeout_s=cfg.SESSION_TIMEOUT_S)
    pipeline = VoicePipeline(cfg, stt, retriever, llm, tts, sessions)

    # Attach to cfg so Flask routes can access them
    cfg._stt      = stt
    cfg._retriever = retriever
    cfg._llm      = llm
    cfg._tts      = tts
    cfg._sessions = sessions
    cfg._pipeline = pipeline

    print()
    print(f"  LLM   : {model or 'not loaded'}")
    print(f"  STT   : faster-whisper/{cfg.WHISPER_MODEL} (+ Denoise)" if cfg.WHISPER_DENOISE else f"  STT   : faster-whisper/{cfg.WHISPER_MODEL}")
    print(f"  TTS   : {engine_name}")
    print(f"  KB    : {len(BANK_KNOWLEDGE)} banking FAQ entries")
    print(f"  URL   : http://localhost:5000")
    print()
