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
    WHISPER_LANGUAGE = "en"       # Force English by default to stop random language hallucinations
    WHISPER_BEAM     = 1           # Greedy decoding (fastest, prevents infinite loop)
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

    # ── LLM (Ollama) ──────────────────────────────────────────
    OLLAMA_HOST    = "http://localhost:11434"
    OLLAMA_MODEL   = "phi3:mini"           # primary model
    OLLAMA_FALLBACK = [                    # tried in order if primary missing
        "phi3:mini", "gemma2:2b", "mistral", "llama3.2", "llama2"
    ]
    LLM_TEMPERATURE = 0.00
    LLM_TOP_P       = 0.9
    LLM_MAX_TOKENS  = 110
    LLM_TIMEOUT_S   = 120
    LLM_STOP        = ["\n\n", "User:", "Human:", "Assistant:"]

    # ── TTS (pyttsx3 + espeak) ────────────────────────────────
    TTS_RATE         = 155         # words per minute (130=slow, 175=fast)
    TTS_VOLUME       = 0.95
    TTS_ENABLE_CACHE = True        # cache rendered WAV files to disk

    # ── RAG (ChromaDB + sentence-transformers) ────────────────
    EMBED_MODEL   = "all-MiniLM-L6-v2"
    RAG_TOP_K     = 3              # how many KB chunks to retrieve
    RAG_COLLECTION = "bank_faq"

    # ── Confidence gate ───────────────────────────────────────
    CONF_THRESHOLD    = 0.20       # below → human teller fallback
    CONF_WEIGHT_STT   = 0.30       # weight of STT confidence (lowered - unreliable on accents)
    CONF_WEIGHT_RAG   = 0.70       # weight of RAG similarity (primary signal)

    # ── Session ───────────────────────────────────────────────
    SESSION_TIMEOUT_S = 120        # seconds idle before auto-reset
    SESSION_MAX_TURNS = 2          # turns kept in context window

    # ── Flask ─────────────────────────────────────────────────
    FLASK_SECRET = "brainback-algonexus-ps02"

    def __init__(self):
        # Create runtime directories
        self.TTS_CACHE_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)
