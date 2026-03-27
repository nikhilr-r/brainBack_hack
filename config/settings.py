"""
config/settings.py
------------------
Central configuration for BrainBack.AI BankBot.
All tunable parameters live here — never scattered across files.
"""

from pathlib import Path


class Settings:
    # ── Project paths ─────────────────────────────────────────
    BASE_DIR      = Path(__file__).parent.parent
    TTS_CACHE_DIR = BASE_DIR / "tts_cache"
    LOG_DIR       = BASE_DIR / "logs"

    # ── STT (faster-whisper) ──────────────────────────────────
    WHISPER_MODEL    = "small"     # small for better noisy environment handling
    WHISPER_DEVICE   = "cpu"       # cpu | cuda
    WHISPER_COMPUTE  = "int8"      # int8 | float16 | float32
    WHISPER_LANGUAGE = None         # None = auto-detect (enables Hindi, Marathi, English)
    WHISPER_BEAM     = 3           # Reduced from 5 for faster inference
    WHISPER_VAD      = True        # Re-enabled: filters noise/silence hallucinations
    WHISPER_PROMPT   = (
        "Bank account, savings account, current account, fixed deposit, FD, "
        "recurring deposit, home loan, personal loan, education loan, gold loan, "
        "KYC documents, Aadhaar card, PAN card, ATM card, debit card, credit card, "
        "block card, cheque book, passbook, NEFT, RTGS, UPI, mobile banking, "
        "net banking, interest rate, minimum balance, "
        "Jan Dhan Yojana, Sukanya Samriddhi, Mudra loan, Kisan Credit Card, "
        "Atal Pension, PPF, NPS, locker, branch timing, complaint, nominee, "
        "open account, close account, transfer money, check balance"
    )
    WHISPER_DENOISE    = True        # Elite: Apply RNNoise/Noisereduce before STT

    # ── LLM (Ollama) ──────────────────────────────────────────
    OLLAMA_HOST    = "http://localhost:11434"
    OLLAMA_MODEL   = "phi3:mini"           # primary model
    OLLAMA_FALLBACK = [                    # tried in order if primary missing
        "phi3:mini", "gemma2:2b", "mistral", "llama3.2", "llama2"
    ]
    LLM_TEMPERATURE = 0.05
    LLM_TOP_P       = 0.9
    LLM_MAX_TOKENS  = 50           # Aggressive limit — keeps answers concise AND fast
    LLM_TIMEOUT_S   = 60
    LLM_STOP        = ["\n\n", "User:", "Human:", "Assistant:"]

    # ── TTS (pyttsx3 + espeak) ────────────────────────────────
    TTS_RATE         = 155         # words per minute (130=slow, 175=fast)
    TTS_VOLUME       = 0.95
    TTS_ENABLE_CACHE = True        # cache rendered WAV files to disk
    TTS_ENGINE       = "elite"     # elite (Sherpa-ONNX) | basic (pyttsx3)
    
    # Elite TTS Model Paths (relative to BASE_DIR/data/models)
    TTS_MODEL_DIR    = BASE_DIR / "data" / "models" / "tts"
    TTS_MODELS = {
        "en": "vits-vctk-en-piper-low.onnx", # High quality English
        "hi": "vits-indic-hindi-female.onnx", # High quality Hindi
        "mr": "vits-indic-marathi-female.onnx" # High quality Marathi
    }
    TTS_TOKENS = "tokens.txt" # Shared tokens for Indic models

    # ── RAG (ChromaDB + sentence-transformers) ────────────────
    EMBED_MODEL   = "all-MiniLM-L6-v2"
    RAG_TOP_K     = 3              # how many KB chunks to retrieve
    RAG_COLLECTION = "bank_faq"

    # ── Confidence gate ───────────────────────────────────────
    CONF_THRESHOLD    = 0.30       # below → human teller fallback
    CONF_WEIGHT_STT   = 0.30       # weight of STT confidence (lowered - unreliable on accents)
    CONF_WEIGHT_RAG   = 0.70       # weight of RAG similarity (primary signal)

    # ── Session ───────────────────────────────────────────────
    SESSION_TIMEOUT_S = 120        # seconds idle before auto-reset
    SESSION_MAX_TURNS = 1          # 1 turn = smallest context = fastest inference

    # ── Flask ─────────────────────────────────────────────────
    FLASK_SECRET = "brainback-algonexus-ps02"

    def __init__(self):
        # Create runtime directories
        self.TTS_CACHE_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)
