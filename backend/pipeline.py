"""
backend/pipeline.py
--------------------
Core voice pipeline — orchestrates all components end to end.

Flow:
  audio_bytes / text
      → STT (Whisper)                  → detects user language
      → RAG retrieval (FAISS)          → always searches in English
      → Confidence gate
      → LLM generation (Ollama)        → always generates in English
      → Translate (deep-translator)    → English → user's language
      → TTS
      → PipelineResult

This module has NO Flask dependency — it can be unit-tested standalone.
"""

import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from config.prompts import SYSTEM_PROMPT, FALLBACK_MESSAGES
from backend.translate import translate_response

log = logging.getLogger("bankbot.pipeline")

# ── Banking Term Correction (STT Garbling → Correct Terms) ─────
# Whisper transliterates Hindi scheme names into garbled English.
# This dictionary maps the common misspellings to correct banking terms.
TERM_CORRECTIONS = {
    # Jan Dhan Yojana variants
    "jindan": "Jan Dhan", "jandhan": "Jan Dhan", "jandan": "Jan Dhan",
    "chandan": "Jan Dhan", "jan dan": "Jan Dhan", "jandhn": "Jan Dhan",
    "jantan": "Jan Dhan", "jendan": "Jan Dhan",
    # Yojana variants
    "yojna": "Yojana", "ehojna": "Yojana", "yogna": "Yojana",
    "yojina": "Yojana", "yojona": "Yojana",
    # Pradhan Mantri variants
    "pradhanmantri": "Pradhan Mantri", "pradhan mantree": "Pradhan Mantri",
    # Scheme name variants
    "sukanya": "Sukanya Samriddhi", "sukaniya": "Sukanya Samriddhi",
    "mudra": "Mudra loan", "mudhra": "Mudra loan",
    "kisan": "Kisan Credit Card", "kishan": "Kisan Credit Card",
    "atal": "Atal Pension", "atl": "Atal Pension",
    "vishwakarma": "PM Vishwakarma", "vishkarma": "PM Vishwakarma",
    "svanidhi": "PM SVANidhi", "swanidhi": "PM SVANidhi",
    # Banking terms
    "fd": "Fixed Deposit", "f.d.": "Fixed Deposit", "fix deposit": "Fixed Deposit",
    "rd": "Recurring Deposit", "r.d.": "Recurring Deposit",
    "kyc": "KYC documents", "k.y.c.": "KYC documents",
    "neft": "NEFT transfer", "rtgs": "RTGS transfer", "upi": "UPI payment",
    "emi": "EMI", "ppf": "PPF Public Provident Fund",
    "nps": "NPS National Pension Scheme",
    "pmjdy": "Pradhan Mantri Jan Dhan Yojana",
    "pmjjby": "Pradhan Mantri Jeevan Jyoti Bima Yojana",
    "pmsby": "Pradhan Mantri Suraksha Bima Yojana",
    "adhar": "Aadhaar", "adhan": "Aadhaar", "aadhaar": "Aadhaar",
    "aadhar": "Aadhaar",
    # Common banking verbs
    "seeds": "schemes", "seed": "scheme",
}


def normalize_query(text: str) -> str:
    """Fix common Whisper transliteration errors before RAG lookup."""
    words = text.split()
    corrected = []
    for word in words:
        clean = word.lower().strip(".,?!;:'\"")
        if clean in TERM_CORRECTIONS:
            corrected.append(TERM_CORRECTIONS[clean])
        else:
            corrected.append(word)
    result = " ".join(corrected)
    if result != text:
        print(f"\033[93m    [CORRECTION] '{text}' → '{result}'\033[0m")
    return result

# ── Zero-Latency Fast Paths: Expanded 30+ Banking FAQ Cache ─────
# These questions return INSTANTLY without any LLM call.
FAST_PATH_CACHE = {
    # Fixed Deposit
    "fd interest rate": {
        "en": "Our Fixed Deposit rates are: 1 year – 6.8%, 2 years – 7.0%, 3 years – 7.1%. Senior citizens get an extra 0.5%.",
        "hi": "हमारी फिक्स्ड डिपॉजिट दरें हैं: 1 साल – 6.8%, 2 साल – 7.0%, 3 साल – 7.1%. वरिष्ठ नागरिकों को 0.5% अतिरिक्त मिलता है।"
    },
    "savings account": {
        "en": "To open a savings account: Aadhaar card, PAN card, and 2 passport-size photos. Minimum balance Rs 1,000.",
        "hi": "बचत खाता खोलने के लिए: आधार कार्ड, पैन कार्ड, 2 पासपोर्ट फोटो। न्यूनतम बैलेंस Rs 1,000।"
    },
    "atm card block": {
        "en": "To block your ATM card, call 1800-XXX-XXXX or visit the branch. A new card will be dispatched in 3 days.",
        "hi": "ATM कार्ड ब्लॉक करने के लिए 1800-XXX-XXXX पर कॉल करें या शाखा आएं। नया कार्ड 3 दिनों में आएगा।"
    },
    "branch timing": {
        "en": "Branch hours: Monday to Friday 10:00 AM – 4:00 PM. 1st, 3rd, 5th Saturday 10:00 AM – 1:00 PM.",
        "hi": "शाखा समय: सोमवार से शुक्रवार 10 बजे से 4 बजे। 1, 3, 5वें शनिवार 10 बजे से 1 बजे।"
    },
    "home loan": {
        "en": "Home loans start at 8.5% per annum, up to 30 years tenure. Documents needed: Aadhaar, PAN, salary slips, property papers.",
        "hi": "होम लोन 8.5% प्रति वर्ष से शुरू, 30 साल तक की अवधि। जरूरी दस्तावेज: आधार, पैन, सैलरी स्लिप, संपत्ति दस्तावेज।"
    },
    "jan dhan": {
        "en": "Jan Dhan account is a zero-balance account with free Rupay debit card, Rs 2 lakh accident insurance, and overdraft up to Rs 10,000.",
        "hi": "जन धन खाता जीरो-बैलेंस खाता है जिसमें मुफ्त रुपे डेबिट कार्ड, 2 लाख दुर्घटना बीमा और 10,000 ओवरड्राफ्ट मिलता है।"
    },
    "gold loan": {
        "en": "Gold loans are available at 9.2% interest. You can get up to 75% of the gold value instantly.",
        "hi": "गोल्ड लोन 9.2% ब्याज पर उपलब्ध है। आप सोने के मूल्य का 75% तुरंत प्राप्त कर सकते हैं।"
    },
    "mudra loan": {
        "en": "Mudra Loan under Pradhan Mantri scheme: Shishu (up to Rs 50,000), Kishore (up to Rs 5 lakh), Tarun (up to Rs 10 lakh). Required: business plan and GST.",
        "hi": "मुद्रा लोन: शिशु (50,000 तक), किशोर (5 लाख), तरुण (10 लाख)। बिज़नेस प्लान और GST जरूरी।"
    },
    "kyc": {
        "en": "For KYC update, you need Aadhaar card, PAN card, and one passport-size photo. Please visit the branch in person.",
        "hi": "KYC अपडेट के लिए आधार कार्ड, पैन कार्ड और एक पासपोर्ट फोटो चाहिए। कृपया शाखा में आएं।"
    },
    "personal loan": {
        "en": "Personal loans start from 10.5% interest for salaried employees. Maximum Rs 10 lakh, tenure up to 5 years.",
        "hi": "पर्सनल लोन 10.5% से शुरू। अधिकतम 10 लाख, 5 साल तक की अवधि।"
    },
    "education loan": {
        "en": "Education loans up to Rs 15 lakh for higher studies in India and Rs 20 lakh for abroad. Interest starts at 8.95%.",
        "hi": "शिक्षा ऋण भारत में 15 लाख और विदेश के लिए 20 लाख तक। ब्याज 8.95% से।"
    },
    "cibil score": {
        "en": "A CIBIL score above 750 is considered excellent. Scores below 600 may affect loan approval. Check your score free at CIBIL.com.",
        "hi": "750 से ऊपर CIBIL स्कोर उत्कृष्ट माना जाता है। 600 से कम स्कोर लोन पर असर डाल सकता है।"
    },
    "upi": {
        "en": "UPI transfers are free and instant, available 24/7. Daily limit is Rs 1 lakh per transaction. Use BHIM, PhonePe or Google Pay.",
        "hi": "UPI ट्रांसफर मुफ्त और तत्काल है, 24/7 उपलब्ध। दैनिक सीमा 1 लाख प्रति लेनदेन।"
    },
    "neft rtgs": {
        "en": "NEFT works batch-wise (24/7 since Dec 2019). RTGS is for transfers above Rs 2 lakh and is real-time. Both are free digitally.",
        "hi": "NEFT बैच में काम करती है (24/7)। RTGS 2 लाख से ऊपर के तुरंत ट्रांसफर के लिए है।"
    },
    "sukanya samriddhi": {
        "en": "Sukanya Samriddhi Yojana gives 8.2% interest for girl child. Open for girls below 10 years. Minimum Rs 250/year.",
        "hi": "सुकन्या समृद्धि योजना बालिकाओं के लिए 8.2% ब्याज देती है। 10 साल से कम उम्र की बालिकाओं के लिए।"
    },
    "ppf": {
        "en": "PPF (Public Provident Fund) offers 7.1% tax-free returns. Rs 500 to Rs 1.5 lakh per year. Lock-in of 15 years.",
        "hi": "PPF 7.1% टैक्स-फ्री रिटर्न देता है। न्यूनतम Rs 500, अधिकतम Rs 1.5 लाख प्रति वर्ष। 15 साल का लॉक-इन।"
    },
    "locker": {
        "en": "Bank locker rent ranges from Rs 1,500 to Rs 8,000 per year depending on size. Visit the branch for availability.",
        "hi": "बैंक लॉकर किराया आकार के अनुसार 1,500 से 8,000 रुपये प्रति वर्ष। उपलब्धता के लिए शाखा आएं।"
    },
    "cheque book": {
        "en": "New cheque book request can be made via net banking, mobile app, or at the branch. Delivered to your registered address in 5-7 days.",
        "hi": "नई चेकबुक नेट बैंकिंग, मोबाइल ऐप या शाखा से मांगी जा सकती है। 5-7 दिनों में पते पर आती है।"
    },
    "recurring deposit": {
        "en": "Recurring Deposit (RD) allows monthly savings from Rs 100. Tenure 6 months to 10 years. Interest rate: 6.5% to 7.5%.",
        "hi": "रेकरिंग डिपॉजिट में मासिक Rs 100 से बचत। 6 महीने से 10 साल की अवधि। ब्याज दर: 6.5% से 7.5%।"
    },
    "current account": {
        "en": "Current accounts are for businesses. No limit on transactions. Minimum balance Rs 10,000. No interest paid on balance.",
        "hi": "करंट अकाउंट व्यवसाय के लिए है। असीमित लेनदेन। न्यूनतम बैलेंस Rs 10,000। बैलेंस पर ब्याज नहीं।"
    },
    "net banking": {
        "en": "Register for net banking at the branch or via mobile app. You can check balance, transfer funds, pay bills 24/7.",
        "hi": "नेट बैंकिंग शाखा या मोबाइल ऐप से पंजीकृत करें। बैलेंस चेक, फंड ट्रांसफर, बिल पेमेंट 24/7।"
    },
    "interest rate": {
        "en": "Our key rates: Savings 3.5%, FD 6.8–7.1%, Home Loan 8.5%, Personal Loan 10.5%, Gold Loan 9.2%.",
        "hi": "मुख्य ब्याज दरें: बचत 3.5%, FD 6.8–7.1%, होम लोन 8.5%, पर्सनल लोन 10.5%, गोल्ड लोन 9.2%।"
    },
    "complaint": {
        "en": "Lodge a complaint at the branch, via net banking, or email care@bank.in. Grievance redressal within 2 working days.",
        "hi": "शिकायत शाखा में, नेट बैंकिंग पर, या care@bank.in पर दर्ज करें। 2 कार्य दिवसों में समाधान।"
    },
    "balance": {
        "en": "Check your account balance via SMS (BAL to 567xx), missed call (1800-xxx-xxx), or net banking.",
        "hi": "बैलेंस SMS (BAL to 567xx), मिस्ड कॉल (1800-xxx-xxx), या नेट बैंकिंग से देखें।"
    },
    "loan eligibility": {
        "en": "Loan eligibility depends on your income, CIBIL score (>700 preferred), age (21–60 years), and employment stability.",
        "hi": "लोन योग्यता: आय, CIBIL स्कोर (700 से अधिक), उम्र (21–60 वर्ष), और रोजगार स्थिरता पर निर्भर।"
    },
    "pm vishwakarma": {
        "en": "PM Vishwakarma scheme provides collateral-free loans to artisans at 5% interest, up to Rs 3 lakh.",
        "hi": "PM विश्वकर्मा योजना कारीगरों को 5% ब्याज पर 3 लाख तक बिना जमानत के लोन देती है।"
    },
    "atal pension": {
        "en": "Atal Pension Yojana gives guaranteed pension from Rs 1,000 to Rs 5,000/month after age 60. Join via bank account.",
        "hi": "अटल पेंशन योजना 60 वर्ष बाद Rs 1,000 से Rs 5,000/माह की गारंटीड पेंशन देती है।"
    },
    "kisan credit card": {
        "en": "Kisan Credit Card provides short-term credit for farmers up to Rs 3 lakh at 7% interest, with 3% subsidy.",
        "hi": "किसान क्रेडिट कार्ड किसानों को 7% ब्याज पर 3 लाख तक क्रेडिट देता है, 3% सब्सिडी के साथ।"
    },
    "nri account": {
        "en": "NRIs can open NRE (tax-free, repatriable) or NRO accounts. Brings foreign income home at best exchange rates.",
        "hi": "NRI NRE (टैक्स-फ्री) या NRO खाता खोल सकते हैं। विदेशी आय सर्वोत्तम दरों पर भारत लाएं।"
    },
    "minimum balance": {
        "en": "Savings account minimum balance: Rs 1,000 (rural), Rs 2,500 (semi-urban), Rs 5,000 (urban). Jan Dhan: zero balance.",
        "hi": "बचत खाता न्यूनतम बैलेंस: Rs 1,000 (ग्रामीण), Rs 2,500 (अर्ध-शहरी), Rs 5,000 (शहरी)।"
    },
}

# ── Fuzzy Cache Match: keywords for each cache key ────────────────
# NOTE: Avoid generic single words ("open", "time", "rate", "score", etc.)
# that can match unrelated queries. Prefer multi-word phrases.
# Each entry has "strong" keywords (1 match = hit) and "weak" keywords (need 2+ matches).
FAST_PATH_KEYWORDS = {
    "fd interest rate": {"strong": ["fixed deposit", "fd interest", "fd rate"], "weak": ["fd", "byaj"]},
    "savings account": {"strong": ["savings account", "saving account", "bachat khata"], "weak": ["savings", "bachat"]},
    "atm card block": {"strong": ["atm card", "card block", "debit card block", "card lost", "card band"], "weak": ["atm"]},
    "branch timing": {"strong": ["branch timing", "branch hours", "bank timing", "branch time", "shaka samay"], "weak": ["branch", "shaka"]},
    "home loan": {"strong": ["home loan", "housing loan", "property loan", "ghar loan"], "weak": ["housing"]},
    "jan dhan": {"strong": ["jan dhan", "jandhan", "jandan", "zero balance account"], "weak": ["pradhan mantri"]},
    "gold loan": {"strong": ["gold loan", "sona loan"], "weak": ["gold", "sona"]},
    "mudra loan": {"strong": ["mudra loan", "mudra", "business loan"], "weak": ["vyapar", "startup"]},
    "kyc": {"strong": ["kyc", "know your customer", "update kyc", "kyc karna"], "weak": []},
    "personal loan": {"strong": ["personal loan", "niji loan", "urgent loan"], "weak": []},
    "education loan": {"strong": ["education loan", "study loan"], "weak": ["college loan", "university loan", "padhai"]},
    "cibil score": {"strong": ["cibil", "credit score", "credit report"], "weak": []},
    "upi": {"strong": ["upi", "google pay", "phonepe", "bhim"], "weak": []},
    "neft rtgs": {"strong": ["neft", "rtgs", "wire transfer", "bank transfer"], "weak": []},
    "sukanya samriddhi": {"strong": ["sukanya", "sukanya samriddhi", "girl child scheme"], "weak": ["beti", "ladki"]},
    "ppf": {"strong": ["ppf", "public provident fund", "public provident"], "weak": ["tax saving"]},
    "locker": {"strong": ["bank locker", "locker", "safe deposit", "tijori"], "weak": []},
    "cheque book": {"strong": ["cheque book", "check book", "chequebook", "cheque"], "weak": []},
    "recurring deposit": {"strong": ["recurring deposit", "monthly deposit"], "weak": ["rd", "masik"]},
    "current account": {"strong": ["current account", "business account"], "weak": ["overdraft"]},
    "net banking": {"strong": ["net banking", "internet banking", "online banking", "mobile banking"], "weak": []},
    "interest rate": {"strong": ["interest rate", "byaj dar"], "weak": ["byaj", "faida"]},
    "complaint": {"strong": ["complaint", "shikayat", "grievance"], "weak": []},
    "balance": {"strong": ["check balance", "account balance", "balance enquiry"], "weak": ["balance", "kitna", "bakiya"]},
    "loan eligibility": {"strong": ["loan eligibility", "loan eligible"], "weak": ["eligibility", "eligible", "qualify"]},
    "pm vishwakarma": {"strong": ["vishwakarma", "pm vishwakarma"], "weak": ["artisan", "karigar"]},
    "atal pension": {"strong": ["atal pension", "pension yojana"], "weak": ["pension", "retirement"]},
    "kisan credit card": {"strong": ["kisan credit", "kisan", "kcc"], "weak": ["farmer", "kisaan", "agriculture"]},
    "nri account": {"strong": ["nri account", "nri", "nre", "nro"], "weak": []},
    "minimum balance": {"strong": ["minimum balance", "min balance", "nyuntam"], "weak": []},
}

def fuzzy_fast_path(query: str, lang: str) -> Optional[str]:
    """Check fast-path cache using keyword matching for near-instant responses.
    
    Uses two-tier matching:
    - "strong" keywords: a single match is enough (these are specific multi-word phrases)
    - "weak" keywords: need 2+ matches to trigger (these are generic single words)
    """
    q = query.lower().strip()
    q_words = set(q.replace(',', ' ').replace('.', ' ').replace('?', ' ').replace('!', ' ').split())
    
    # 1. Direct exact match in cache keys (very specific, safe)
    for key in FAST_PATH_CACHE:
        if key in q:
            return FAST_PATH_CACHE[key].get(lang) or FAST_PATH_CACHE[key].get("en")
    
    # 2. Two-tier keyword match
    for key, kw_dict in FAST_PATH_KEYWORDS.items():
        strong_kws = kw_dict.get("strong", [])
        weak_kws = kw_dict.get("weak", [])
        
        # Strong match: any strong keyword phrase found in query → instant hit
        if any(kw in q for kw in strong_kws):
            lang_resp = FAST_PATH_CACHE.get(key, {})
            return lang_resp.get(lang) or lang_resp.get("en")
        
        # Weak match: need at least 2 weak keyword word-level matches
        weak_hits = sum(1 for kw in weak_kws if kw in q_words)
        if weak_hits >= 2:
            lang_resp = FAST_PATH_CACHE.get(key, {})
            return lang_resp.get(lang) or lang_resp.get("en")
    
    return None

FAST_PATH_LOOKUP = {k.lower().strip(" .?!,"): k for k in FAST_PATH_CACHE.keys()}

# ── Language helpers ──────────────────────────────────────────

def detect_lang_from_text(text: str) -> str:
    """Heuristic: Devanagari codepoints → Hindi."""
    return "hi" if any('\u0900' <= c <= '\u097F' for c in text) else "en"


def compute_confidence(stt_conf: float, rag_sim: float,
                       w_stt: float = 0.45, w_rag: float = 0.55) -> float:
    return w_stt * stt_conf + w_rag * rag_sim


# ── Result dataclass ──────────────────────────────────────────

@dataclass
class PipelineResult:
    session_id:   str
    user_text:    str
    bot_text:     str
    lang:         str
    action:       str        # "answer" | "teller_alert" | "no_speech"
    confidence:   dict       = field(default_factory=dict)
    context_used: str        = ""
    audio_b64:    Optional[str] = None
    audio_format: str        = "wav"
    latency_s:    float      = 0.0
    turn:         int        = 0
    llm_model:    str        = "unknown"

    def to_dict(self) -> dict:
        return {
            "session_id":   self.session_id,
            "user_text":    self.user_text,
            "bot_text":     self.bot_text,
            "lang":         self.lang,
            "action":       self.action,
            "confidence":   self.confidence,
            "context_used": self.context_used,
            "audio_b64":    self.audio_b64,
            "audio_format": self.audio_format,
            "latency_s":    self.latency_s,
            "turn":         self.turn,
            "llm_model":    self.llm_model,
        }


# ── Pipeline ──────────────────────────────────────────────────

class VoicePipeline:
    """
    Orchestrates: STT → RAG → Confidence gate → LLM → TTS

    All component instances are injected (no tight coupling).
    """

    def __init__(self, cfg, stt, retriever, llm, tts, sessions):
        self.cfg       = cfg
        self.stt       = stt
        self.retriever = retriever
        self.llm       = llm
        self.tts       = tts
        self.sessions  = sessions

    # ── Public API ────────────────────────────────────────────

    def process_audio(self, audio_bytes: bytes, session_id: str, target_lang: str = "auto") -> PipelineResult:
        """Full pipeline from raw audio bytes."""
        t0 = time.time()
        print(f"\n\033[96m[0/4] Audio received ({len(audio_bytes)} bytes). Running Whisper STT...\033[0m")
        
        # Let Whisper auto-detect language (Hindi, English, Marathi, etc.)
        # `target_lang` from UI is only used as an override when the user manually selected a language
        stt_result = self.stt.transcribe(
            audio_bytes,
            force_language=target_lang if target_lang != "auto" else "auto"
        )

        if not stt_result.success:
            print(f"\033[91m[X] STT Failed -> No speech detected (returned to frontend)\033[0m\n")
            return PipelineResult(
                session_id=session_id,
                user_text="", bot_text="",
                lang="en", action="no_speech",
                latency_s=round(time.time() - t0, 2),
            )

        # Use the language Whisper actually detected as the OUTPUT language.
        # If the user speaks Hindi, lang="hi" -> response will be in Hindi.
        # If the user speaks English, lang="en" -> response will be in English.
        lang = stt_result.language or "en"
        print(f"\033[96m    [LANG] Detected language: {lang}\033[0m")

        return self._run(
            session_id=session_id,
            user_text=stt_result.text,
            lang=lang,
            target_lang=target_lang,
            stt_conf=stt_result.confidence,
            t0=t0,
        )

    def process_text(self, text: str, session_id: str, target_lang: str = "auto") -> PipelineResult:
        """Pipeline from plain text (sample tiles / keyboard input)."""
        t0   = time.time()
        lang = detect_lang_from_text(text) if target_lang == "auto" else target_lang

        return self._run(
            session_id=session_id,
            user_text=text,
            lang=lang,
            target_lang=target_lang,
            stt_conf=0.95,   # text input — treat as high confidence
            t0=t0,
        )

    # ── Internal orchestration ────────────────────────────────

    def _run(self, session_id: str, user_text: str,
             lang: str, target_lang: str, stt_conf: float, t0: float) -> PipelineResult:

        session = self.sessions.get(session_id)
        session.language = lang
        
        print(f"\n\033[94m==> User Input: '{user_text}'\033[0m")

        # ── FAST PATH CACHE (Zero Latency — Fuzzy Keyword Match) ──
        reply_lang = "hi" if lang == "hi" else "en"
        fast_reply = fuzzy_fast_path(user_text, reply_lang)
        if fast_reply:
            print("\033[92m[⚡] Fast-Path Cache Hit (Fuzzy) -> Skipping LLM & RAG\033[0m")
            session.add_turn(user_text, fast_reply)
            audio_b64 = None
            wav = self.tts.synthesize(fast_reply, reply_lang)
            if wav:
                audio_b64 = base64.b64encode(wav).decode()
            return PipelineResult(
                session_id=session_id,
                user_text=user_text,
                bot_text=fast_reply,
                lang=reply_lang,
                action="answer",
                confidence={"stt": round(stt_conf, 3), "rag": 1.0, "overall": 1.0},
                context_used="System Fast-Path Cache",
                audio_b64=audio_b64,
                audio_format="wav",
                latency_s=round(time.time() - t0, 2),
                turn=session.turn_count,
                llm_model="fast-path-cache",
            )

        # 1. RAG retrieval
        corrected_text = normalize_query(user_text)
        print("\033[96m[1/4] Retrieving context from offline database (RAG)...\033[0m")
        rag_result   = self.retriever.retrieve(corrected_text)
        context_str  = "\n".join([doc for doc in rag_result.documents])
        print(f"\033[90m    [RAG] Retrieved {len(rag_result.documents)} docs | Similarity: {rag_result.similarity:.2f}\033[0m")
        for i, doc in enumerate(rag_result.documents):
            print(f"\033[90m    [RAG] Doc {i+1}: '{doc[:80]}...'\033[0m")

        # 2. Confidence gate
        stt_conf = max(0.0, min(1.0, stt_conf))
        rag_conf = rag_result.similarity
        overall_conf = compute_confidence(stt_conf, rag_conf, self.cfg.CONF_WEIGHT_STT, self.cfg.CONF_WEIGHT_RAG)
        print(f"\033[90m    [CONF] STT={stt_conf:.2f} RAG={rag_conf:.2f} Overall={overall_conf:.2f} (threshold={self.cfg.CONF_THRESHOLD})\033[0m")

        if overall_conf < self.cfg.CONF_THRESHOLD:
            print(f"\033[91m[2/4] Confidence too low ({overall_conf:.2f} < {self.cfg.CONF_THRESHOLD}) -> Routing to Human Teller.\033[0m")
            session.add_turn(user_text, "User routed to teller.")
            bot_text    = FALLBACK_MESSAGES.get(lang, FALLBACK_MESSAGES["en"])
            llm_model   = "fallback"
            action      = "teller_alert"
            context_out = ""
        elif rag_conf >= 0.85:
            # ── RAG-Direct Fast Path (Zero LLM) — only for VERY high similarity ──
            print(f"\033[92m[2/4] RAG-Direct Hit (sim={rag_conf:.2f}) ⚡ Skipping LLM!\033[0m")
            # Use all retrieved docs for a more complete answer
            all_docs_text = " ".join(doc.strip() for doc in rag_result.documents if doc.strip())
            sentences = all_docs_text.replace(". ", ".\n").split("\n")
            bot_text = " ".join(s.strip() for s in sentences[:5] if s.strip())
            if not bot_text:
                bot_text = all_docs_text[:300]
            bot_text = bot_text.rstrip(".") + ". Is there anything else I can help you with?"
            action      = "answer"
            context_out = rag_result.context
            llm_model   = "rag-direct"
            session.add_turn(user_text, bot_text)
            print(f"\033[92m[3/4] RAG-Direct Response: '{bot_text[:100]}...'\033[0m")
        else:
            # Resolve language: ALWAYS use STT-detected language.
            # The UI override is only used when STT is uncertain (lang=="auto").
            # This prevents forcing Hindi when user actually spoke English.
            if lang in ("hi", "en"):
                active_lang = lang        # STT knows best
            elif target_lang in ("hi", "en"):
                active_lang = target_lang # Fall back to UI override
            else:
                active_lang = "en"        # Default to English

            # phi3:mini cannot generate proper Hindi — fall back to English
            llm_name = (self.llm.active_model or "").lower()
            if active_lang == "hi" and ("phi3" in llm_name or "phi" in llm_name):
                print("\033[93m    [LANG] phi3 can't do Hindi reliably — using English\033[0m")
                active_lang = "en"

            if active_lang == "hi":
                lang_rule = "CRITICAL RULE: Respond EXCLUSIVELY in HINDI. Your entire response MUST be written in Devanagari script."
            else:
                lang_rule = "CRITICAL RULE: Respond EXCLUSIVELY in ENGLISH. Your entire response MUST be written in English characters only."

            # 3. LLM Generation — send only the single best RAG doc
            filled_prompt = SYSTEM_PROMPT.format(
                context=rag_result.top_context,   # ← only #1 doc, prevents confusion
                language_rule=lang_rule,
            )
            print(f"\033[90m    [LLM] Context sent to model:\033[0m")
            print(f"\033[90m    {rag_result.top_context}\033[0m")
            print(f"\033[90m    [LLM] User message to model: '{corrected_text}'\033[0m")
            try:
                # LLM always generates in English — we translate AFTER
                bot_text_en = self.llm.generate(
                    system_prompt=filled_prompt,
                    user_text=corrected_text,
                    history=[],  # No history: saves tokens, prevents 500 OOM
                )
                bot_text_en += " Do you have any other questions?"

                # Translate English → user's language
                print(f"\033[90m    [TRANSLATE] en → {lang}\033[0m")
                bot_text = translate_response(bot_text_en, lang)

                print(f"\033[92m[3/4] LLM Response ({lang}): '{bot_text}'\033[0m")
                action      = "answer"
                context_out = rag_result.context
                session.add_turn(user_text, bot_text)
            except Exception as e:
                log.error("LLM error: %s", e)
                print(f"\033[91m    [LLM] Error — falling back to RAG context directly\033[0m")
                # Use top RAG doc directly, then translate
                if rag_result and rag_result.top_context:
                    bot_text_en = rag_result.top_context.lstrip('• ')
                    bot_text    = translate_response(bot_text_en, lang)
                    action      = "answer"
                    context_out = rag_result.context
                    session.add_turn(user_text, bot_text)
                else:
                    bot_text    = FALLBACK_MESSAGES.get(lang, FALLBACK_MESSAGES["en"])
                    action      = "teller_alert"
                    context_out = ""

        # 5. TTS
        print("\033[95m[4/4] Bypassing Python Audio Compression -> Transferring to Browser TTS\033[0m")
        audio_b64 = None

        return PipelineResult(
            session_id   = session_id,
            user_text    = user_text,
            bot_text     = bot_text,
            lang         = lang,
            action       = action,
            confidence   = {
                "stt":     round(stt_conf,     3),
                "rag":     round(rag_result.similarity, 3),
                "overall": round(overall_conf, 3),
            },
            context_used = context_out,
            audio_b64    = audio_b64,
            audio_format = "wav",
            latency_s    = round(time.time() - t0, 2),
            turn         = session.turn_count,
            llm_model    = self.llm.active_model or "unavailable",
        )
