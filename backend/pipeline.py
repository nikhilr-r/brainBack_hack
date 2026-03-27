"""
backend/pipeline.py
--------------------
Core voice pipeline — orchestrates all components end to end.

Flow:
  audio_bytes / text
      → STT (Whisper)
      → Confidence check
      → RAG retrieval (ChromaDB)
      → Confidence gate
      → LLM generation (Ollama)
      → TTS (pyttsx3)
      → PipelineResult

This module has NO Flask dependency — it can be unit-tested standalone.
"""

import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from config.prompts import SYSTEM_PROMPT, FALLBACK_MESSAGES

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

# ── Zero-Latency Fast Paths (UI Mockups) ──────────────────────
FAST_PATH_CACHE = {
    "FD interest rate kya hai": {
        "en": "Our current Fixed Deposit interest rate is up to 7.1% per annum for general citizens.",
        "hi": "हमारे फिक्स्ड डिपॉजिट पर सामान्य नागरिकों के लिए 7.1% तक की ब्याज दर है।",
        "mr": "आमचा सध्याचा मुदत ठेव (FD) व्याजदर सामान्य नागरिकांसाठी वार्षिक ७.१% पर्यंत आहे.",
        "gu": "સામાન્ય નાગરિકો માટે અમારો ફિક્સ્ડ ડિપોઝિટ વ્યાજ દર વાર્ષિક 7.1% સુધી છે.",
        "bn": "সাধারণ নাগরিকদের জন্য আমাদের বর্তমান ফিক্সড ডিপোজিট সুদের হার বার্ষিক ৭.১% পর্যন্ত।",
        "ta": "பொது குடிமக்களுக்கான எங்கள் தற்போதைய நிரந்தர வைப்பு வட்டி விகிதம் ஆண்டுக்கு 7.1% வரை உள்ளது.",
        "te": "సాధారణ పౌరులకు మా ప్రస్తుత ఫిక్స్‌డ్ డిపాజిట్ వడ్డీ రేటు సంవత్సరానికి 7.1% వరకు ఉంది.",
        "kn": "ಸಾಮಾನ್ಯ ನಾಗರಿಕರಿಗೆ ನಮ್ಮ ಪ್ರಸ್ತುತ ಸ್ಥಿರ ಠೇವಣಿ ಬಡ್ಡಿ ದರವು ವಾರ್ಷಿಕ 7.1% ವರೆಗೆ ಇದೆ."
    },
    "savings account kholne ke liye kya chahiye": {
        "en": "To open a savings account, you need your Aadhaar card, PAN card, and 2 passport-size photos.",
        "hi": "बचत खाता खोलने के लिए आपको अपना आधार कार्ड, पैन कार्ड और 2 पासपोर्ट साइज फोटो चाहिए।",
        "mr": "बचत खाते उघडण्यासाठी तुम्हाला आधार कार्ड, पॅन कार्ड आणि २ पासपोर्ट आकाराचे फोटो लागतील.",
        "gu": "બચત ખાતું ખોલવા માટે, તમારે તમારું આધાર કાર્ડ, પાન કાર્ડ અને 2 પાસપોર્ટ-સાઇઝ ફોટાની જરૂર છે.",
        "bn": "সেভিংস অ্যাকাউন্ট খোলার জন্য আপনার আধার কার্ড, প্যান কার্ড এবং ২ কপি পাসপোর্ট সাইজ ছবি লাগবে।",
        "ta": "சேமிப்பு கணக்கு திறக்க உங்கள் ஆதார் அட்டை, பான் அட்டை மற்றும் 2 பாஸ்போர்ட் அளவு புகைப்படங்கள் தேவை.",
        "te": "పొదుపు ఖాతా తెరవడానికి, మీకు ఆధార్ కార్డ్, పాన్ కార్డ్ మరియు 2 పాస్‌పోర్ట్ సైజ్ ఫోటోలు అవసరం.",
        "kn": "ಉಳಿತಾಯ ಖಾತೆಯನ್ನು ತೆರೆಯಲು, ನಿಮ್ಮ ಆಧಾರ್ ಕಾರ್ಡ್, ಪ್ಯಾನ್ ಕಾರ್ಡ್ ಮತ್ತು 2 ಪಾಸ್‌ಪೋರ್ಟ್ ಗಾತ್ರದ ಫೋಟೋಗಳು ಬೇಕಾಗುತ್ತವೆ."
    },
    "ATM card block karna hai": {
        "en": "I have blocked your ATM card. The new card will be dispatched to your registered address within 3 days.",
        "hi": "मैंने आपका एटीएम कार्ड ब्लॉक कर दिया है। नया कार्ड 3 दिनों के भीतर आपके पते पर भेज दिया जाएगा।",
        "mr": "मी तुमचे एटीएम कार्ड ब्लॉक केले आहे. नवीन कार्ड ३ दिवसांत तुमच्या नोंदणीकृत पत्त्यावर पाठवले जाईल.",
        "gu": "મેં તમારું એટીએમ કાર્ડ બ્લોક કરી દીધું છે. નવું કાર્ડ 3 દિવસમાં તમારા નોંધાયેલા સરનામા પર મોકલવામાં આવશે.",
        "bn": "আমি আপনার এটিএম কার্ড ব্লক করেছি। নতুন কার্ড ৩ দিনের মধ্যে আপনার নিবন্ধিত ঠিকানায় পাঠানো হবে।",
        "ta": "உங்கள் ஏடிஎம் கார்டை முடக்கியுள்ளேன். புதிய கார்டு 3 நாட்களுக்குள் உங்கள் பதிவு செய்யப்பட்ட முகவரிக்கு அனுப்பப்படும்.",
        "te": "నేను మీ ఏటీఎం కార్డును బ్లాక్ చేసాను. కొత్త కార్డ్ 3 రోజుల్లో మీ నమోదిత చిరునామాకు పంపబడుతుంది.",
        "kn": "ನಾನು ನಿಮ್ಮ ಎಟಿಎಂ ಕಾರ್ಡ್ ಅನ್ನು ಬ್ಲಾಕ್ ಮಾಡಿದ್ದೇನೆ. ಹೊಸ ಕಾರ್ಡ್ ಅನ್ನು 3 ದಿನಗಳಲ್ಲಿ ನಿಮ್ಮ ನೋಂದಾಯಿತ ವಿಳಾಸಕ್ಕೆ ಕಳುಹಿಸಲಾಗುತ್ತದೆ."
    },
    "branch timing kya hai": {
        "en": "The branch is open from 10:00 AM to 4:00 PM on all weekdays, and up to 1:00 PM on 1st, 3rd and 5th Saturdays.",
        "hi": "शाखा सुबह 10:00 बजे से शाम 4:00 बजे तक और पहले, तीसरे और पांचवें शनिवार को दोपहर 1:00 बजे तक खुली रहती है।",
        "mr": "शाखा सर्व कामकाजाच्या दिवशी सकाळी १०:०० ते संध्याकाळी ४:०० पर्यंत आणि १ल्या, ३ऱ्या आणि ५व्या शनिवारी दुपारी १:०० पर्यंत खुली असते.",
        "gu": "શાખા કામકાજના દિવસોમાં સવારે 10:00 થી સાંજે 4:00 સુધી, અને 1લા, 3જા અને 5મા શનિવારે બપોરે 1:00 સુધી ખુલ્લી રહે છે.",
        "bn": "শাখাটি সপ্তাহের দিনগুলিতে সকাল ১০:০০ টা থেকে বিকেল ৪:০০ টা পর্যন্ত এবং ১ম, ৩য় এবং ৫ম শনিবার দুপুর ১:০০ টা পর্যন্ত খোলা থাকে।",
        "ta": "கிளை வார நாட்களில் காலை 10:00 மணி முதல் மாலை 4:00 மணி வரையும், 1வது, 3வது மற்றும் 5வது சனிக்கிழமைகளில் மதியம் 1:00 மணி வரையும் திறந்திருக்கும்.",
        "te": "బ్రాంచ్ పనిదినాల్లో ఉదయం 10:00 నుండి సాయంత్రం 4:00 వరకు మరియు 1 వ, 3 వ మరియు 5 వ శనివారాలలో మధ్యాహ్నం 1:00 వరకు తెరచి ఉంటుంది.",
        "kn": "ಬ್ಯಾಂಕ್ ಬೆಳಿಗ್ಗೆ 10:00 ರಿಂದ ಸಂಜೆ 4:00 ರವರೆಗೆ ಮತ್ತು 1ನೇ, 3ನೇ ಹಾಗೂ 5ನೇ ಶನಿವಾರದಂದು ಮಧ್ಯಾಹ್ನ 1:00 ರವರೆಗೆ ತೆರೆದಿರುತ್ತದೆ."
    },
    "home loan ki jankari": {
        "en": "We offer home loans starting from 8.5% interest rate with a tenure of up to 30 years.",
        "hi": "हम 8.5% ब्याज दर से शुरू होने वाले होम लोन देते हैं, जिसकी अवधि 30 साल तक होती है।",
        "mr": "आम्ही ८.५% व्याजदरापासून ३० वर्षांपर्यंतच्या कालावधीसह गृहकर्ज (होम लोन) देतो.",
        "gu": "અમે 8.5% વ્યાજ દરથી શરૂ થતી હોમ લોન 30 વર્ષ સુધીની મુદત સાથે પ્રદાન કરીએ છીએ.",
        "bn": "আমরা ৮.৫% সুদের হারে বাড়ি কেনার ঋণ (হোম লোন) প্রদান করি, যা ৩০ বছর মেয়াদ পর্যন্ত হতে পারে।",
        "ta": "நாங்கள் 8.5% வட்டி விகிதத்தில் தொடங்கி 30 ஆண்டுகள் வரையிலான பதவிக்காலத்துடன் வீட்டுக் கடன்களை வழங்குகிறோம்.",
        "te": "మేము 8.5% వడ్డీ రేటుతో మొదలయ్యే గృహ రుణాలను 30 సంవత్సరాల కాలపరిమితితో అందిస్తున్నాము.",
        "kn": "ನಾವು 8.5% ಬಡ್ಡಿ ದರದಿಂದ ಆರಂಭವಾಗುವ ಗೃಹ ಸಾಲಗಳನ್ನು 30 ವರ್ಷಗಳ ಅವಧಿಯವರೆಗೆ ನೀಡುತ್ತೇವೆ."
    },
    "Jan Dhan account kya hota hai": {
        "en": "A Jan Dhan account is a zero-balance savings account providing financial access with free Rupay debit card.",
        "hi": "जन धन खाता एक जीरो-बैलेंस बचत खाता है जिसमें मुफ्त रुपे डेबिट कार्ड की सुविधा मिलती है।",
        "mr": "जन धन खाते हे शून्य-शिल्लक (झिरो बॅलेन्स) बचत खाते आहे ज्यामध्ये मोफत रुपे डेबिट कार्ड मिळते.",
        "gu": "જન ધન ખાતું એક ઝીરો-બેલેન્સ બચત ખાતું છે જે મફત રૂપે ડેબિટ કાર્ડ સાથે આવે છે.",
        "bn": "জন ধন অ্যাকাউন্ট হল একটি জিরো-ব্যালেন্স সেভিংস অ্যাকাউন্ট যা বিনামূল্যে রুপে ডেবিট কার্ড প্রদান করে।",
        "ta": "ஜன் தன் கணக்கு என்பது இலவச ரூபே டெபிட் கார்டு வசதியுடன் கூடிய பூஜ்ஜிய-இருப்பு சேமிப்பு கணக்கு ஆகும்.",
        "te": "జన్ ధన్ ఖాతా అనేది ఉచిత రూపే డెబిట్ కార్డ్ సౌకర్యంతో కూడిన జీరో-బ్యాలెన్స్ సేవింగ్స్ ఖాతా.",
        "kn": "ಜನ್ ಧನ್ ಖಾತೆಯು ಉಚಿತ ರುಪೇ ಡೆಬಿಟ್ ಕಾರ್ಡ್ ಸೌಲಭ್ಯದೊಂದಿಗೆ ಬರುವ ಶೂನ್ಯ-ಬ್ಯಾಲೆನ್ಸ್ ಉಳಿತಾಯ ಖಾತೆ ಆಗಿದೆ."
    },
    "gold loan chahiye": {
        "en": "You can pledge your gold jewelry for an instant loan with interest rates starting at 9.2%.",
        "hi": "आप अपने सोने के आभूषण गिरवी रखकर 9.2% ब्याज दर से तुरंत ऋण प्राप्त कर सकते हैं।",
        "mr": "तुम्ही तुमची सोन्याची आभूषणे तारण ठेवून ९.२% व्याजदराने त्वरित कर्ज मिळवू शकता.",
        "gu": "તમે તમારા સોનાના દાગીના ગીરવે મૂકીને 9.2% વ્યાજ દરે તાત્કાલિક લોન મેળવી શકો છો.",
        "bn": "আপনি আপনার সোনার গয়না বন্ধক রেখে ৯.২% সুদের হারে তাত্ক্ষণিক ঋণ পেতে পারেন।",
        "ta": "நீங்கள் உங்கள் தங்க நகைகளை அடகு வைத்து 9.2% வட்டி விகிதத்தில் உடனடியாக கடன் பெறலாம்.",
        "te": "మీరు మీ బంగారు ఆభరణాలను కుదువ పెట్టి 9.2% వడ్డీ రేటుతో తక్షణ రుణాన్ని పొందవచ్చు.",
        "kn": "ನಿಮ್ಮ ಚಿನ್ನದ ಆಭರಣಗಳನ್ನು ಒತ್ತೆ ಇಡುವ ಮೂಲಕ 9.2% ಬಡ್ಡಿ ದರದಲ್ಲಿ ತ್ವರಿತ ಸಾಲ ಪಡೆಯಬಹುದು."
    },
    "mudra loan kaise milega": {
        "en": "Mudra loans require a solid business plan and GST registration. Please visit the branch for the exact paperwork.",
        "hi": "मुद्रा लोन के लिए एक ठोस व्यापार योजना और जीएसटी पंजीकरण की आवश्यकता होती है। कागजी कार्रवाई के लिए कृपया शाखा आएं।",
        "mr": "मुद्रा कर्जासाठी ठोस व्यवसाय योजना आणि जीएसटी नोंदणी आवश्यक आहे. कागदपत्रांसाठी कृपया बँकेच्या शाखेला भेट द्या.",
        "gu": "મુદ્રા લોન માટે નક્કર વ્યવસાય યોજના અને જીએસટી નોંધણી જરૂરી છે. દસ્તાવેજો માટે કૃપા કરીને શાખાની મુલાકાત લો.",
        "bn": "মুদ্রা লোনের জন্য একটি শক্ত ব্যবসা পরিকল্পনা এবং জিএসটি নিবন্ধন প্রয়োজন। কাগজপত্র জমা দিতে দয়া করে শাখায় আসুন।",
        "ta": "முத்ரா கடன் பெற சரியான வணிகத் திட்டம் மற்றும் ஜிஎஸ்டி பதிவு தேவை. ஆவணங்களுக்கு கிளைக்கு வரவும்.",
        "te": "ముద్రా రుణాల కోసం వృత్తి ప్రణాళిక మరియు జిఎస్‌టి నమోదు తప్పనిసరి. పత్రాల కోసం దయచేసి బ్రాంచ్‌ను సందర్శించండి.",
        "kn": "ಮುದ್ರಾ ಸಾಲಕ್ಕಾಗಿ ಉತ್ತಮ ವ್ಯಾಪಾರ ಯೋಜನೆ ಮತ್ತು ಜಿಎಸ್‌ಟಿ ನೋಂದಣಿ ಅಗತ್ಯವಿದೆ. ಹೆಚ್ಚಿನ ಮಾಹಿತಿಗಾಗಿ ಬ್ಯಾಂಕ್ ಶಾಖೆಯನ್ನು ಭೇಟಿ ಮಾಡಿ."
    }
}

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
        
        # We now use a multilingual embedder, so we transcribe natively in the selected language.
        # This completely stops Whisper from hallucinating during forced translation.
        stt_result = self.stt.transcribe(audio_bytes, force_language=target_lang)

        if not stt_result.success:
            print(f"\033[91m[X] STT Failed -> No speech detected (returned to frontend)\033[0m\n")
            return PipelineResult(
                session_id=session_id,
                user_text="", bot_text="",
                lang="en", action="no_speech",
                latency_s=round(time.time() - t0, 2),
            )

        # Use target_lang for LLM output; STT is always English
        lang = "en" if target_lang == "auto" else target_lang

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

        # ── FAST PATH CACHE (Zero Latency) ──
        norm_text = user_text.lower().strip(" .?!,")
        if norm_text in FAST_PATH_LOOKUP:
            print("\033[92m[⚡] Fast-Path Cache Hit -> Skipping LLM & RAG\033[0m")
            orig_key = FAST_PATH_LOOKUP[norm_text]
            ans_dict = FAST_PATH_CACHE[orig_key]
            
            reply_lang = lang if lang in ans_dict else "en"
            bot_text = ans_dict[reply_lang]
            session.add_turn(user_text, bot_text)

            audio_b64 = None
            wav = self.tts.synthesize(bot_text, reply_lang)
            if wav:
                audio_b64 = base64.b64encode(wav).decode()

            return PipelineResult(
                session_id=session_id,
                user_text=user_text,
                bot_text=bot_text,
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
            print("\033[92m[✔] Pipeline Complete\033[0m\n")
            return result
   

        # 0. LLM Query Correction (fixes Whisper's rough English translations from regional audio)
        if lang not in ["en", "auto"]:
            print(f"\n\033[96m[0.5] Correcting Whisper translation for {lang} query...\033[0m")
            correction_system = "You are a banking query corrector. The user's text is a rough English translation from regional Indian language audio. Fix spelling errors, correct banking terms, and output a clean English banking question. Output ONLY the corrected English question. Do NOT answer it. Do NOT explain."
            few_shot = [
                {"user": "I don't know how to change the loan.", "bot": "How do I change or transfer my loan?"},
                {"user": "I have to open a new hand. How much money does it need?", "bot": "I want to open a new bank account. What is the minimum deposit needed?"},
                {"user": "I am very happy to see that this is the last time I have spoken in a bank.", "bot": "I want to close my bank account. What is the process?"},
                {"user": "I want to transfer my name from my bank to another bank.", "bot": "How do I transfer my bank account to another branch?"},
                {"user": "What documents are needed to open a saving account?", "bot": "What documents are needed to open a savings account?"},
                {"user": "The world is a stage", "bot": "What is a Jan Dhan account?"},
                {"user": "I have been updating my KYC for the past few days.", "bot": "How do I update my KYC documents?"},
            ]
            rag_query = self.llm.generate(
                system_prompt=correction_system,
                user_text=user_text,
                history=few_shot,
            )
            rag_query = rag_query.strip(" \n'\"")
            # If LLM returns something too long or suspicious, fallback to original
            if len(rag_query) > 150 or len(rag_query) < 3:
                rag_query = user_text
            print(f"\033[90m    [Query Correction] '{user_text}' -> '{rag_query}'\033[0m")
        else:
            rag_query = user_text

        # 1. RAG retrieval
        corrected_text = normalize_query(rag_query)
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
        else:
            print(f"\033[93m[2/4] Confidence OK ({overall_conf:.2f}). Starting LLM inference (may take 10-15s on CPU)...\033[0m")
            
            # Resolve automatic target constraints explicitly
            active_lang = lang if target_lang == "auto" else target_lang

            LANG_MAP = {
                "en": {"name": "ENGLISH", "script": "English characters"},
                "hi": {"name": "HINDI", "script": "Devanagari script"},
                "mr": {"name": "MARATHI", "script": "Devanagari script"},
                "gu": {"name": "GUJARATI", "script": "Gujarati script"},
                "bn": {"name": "BENGALI", "script": "Bengali script"},
                "ta": {"name": "TAMIL", "script": "Tamil script"},
                "te": {"name": "TELUGU", "script": "Telugu script"},
                "kn": {"name": "KANNADA", "script": "Kannada script"},
                "ml": {"name": "MALAYALAM", "script": "Malayalam script"},
                "pa": {"name": "PUNJABI", "script": "Gurmukhi script"},
                "or": {"name": "ODIA", "script": "Odia script"},
                "as": {"name": "ASSAMESE", "script": "Assamese script"}
            }
            lang_info = LANG_MAP.get(active_lang, LANG_MAP["en"])
            lang_rule = f"CRITICAL RULE: Respond EXCLUSIVELY in {lang_info['name']}. Your entire response MUST stringently be written in {lang_info['script']}."
            if active_lang == "mr":
                lang_rule += " You are speaking Marathi, NOT Hindi. You MUST strictly use Marathi grammar and vocabulary (e.g. 'माहिती नाही', 'आवश्यक आहे', 'कसे'). NEVER output Hindi words."

            # 3. LLM Generation
            filled_prompt = SYSTEM_PROMPT.format(
                context=rag_result.context,
                language_rule=lang_rule,
            )
            print(f"\033[90m    [LLM] Context sent to model:\033[0m")
            print(f"\033[90m    {rag_result.context[:200]}...\033[0m")
            print(f"\033[90m    [LLM] User message to model: '{corrected_text}'\033[0m")
            try:
                bot_text = self.llm.generate(
                    system_prompt=filled_prompt,
                    user_text=corrected_text,
                    history=session.get_history_dicts(self.cfg.SESSION_MAX_TURNS),
                )
                
                # Append standard "Any more questions?" prompt
                SUFFIX_MAP = {
                    "en": " Do you have any other questions?",
                    "hi": " क्या आपके पास कोई और सवाल है?",
                    "mr": " तुम्हाला आणखी काही प्रश्न आहेत का?",
                    "gu": " શું તમને કોઈ અન્ય પ્રશ્નો છે?",
                    "bn": " আপনার কি আর কোন প্রশ্ন আছে?",
                    "ta": " உங்களுக்கு வேறு ஏதேனும் கேள்விகள் உள்ளதா?",
                    "te": " మీకు ఇంకేమైనా ప్రశ్నలు ఉన్నాయా?",
                    "kn": " ನಿಮಗೆ ಬೇರೆ ಏನಾದರೂ ಪ್ರಶ್ನೆಗಳಿವೆಯೇ?",
                    "ml": " നിങ്ങൾക്ക് വേറെ എന്തെങ്കിലും ചോദ്യങ്ങളുണ്ടോ?",
                    "pa": " ਕੀ ਤੁਹਾਡੇ ਕੋਈ ਹੋਰ ਸਵਾਲ ਹਨ?",
                    "or": " ଆପଣଙ୍କର ଅନ୍ୟ କୌଣସି ପ୍ରଶ୍ନ ଅଛି କି?",
                    "as": " আপোনাৰ আন কিবা প্ৰশ্ন আছে নেকি?"
                }
                clean_bot_text = bot_text
                bot_text += SUFFIX_MAP.get(active_lang, SUFFIX_MAP["en"])
                    
                print(f"\033[92m[3/4] LLM Response: '{bot_text}'\033[0m")
                action      = "answer"
                context_out = rag_result.context
                session.add_turn(user_text, clean_bot_text)
            except Exception as e:
                log.error("LLM error: %s", e)
                bot_text    = FALLBACK_MESSAGES.get(lang, FALLBACK_MESSAGES["en"])
                action      = "teller_alert"
                context_out = ""

        # 5. TTS
        print("\033[95m[4/4] Generating Offline/Cloud TTS Audio\033[0m")
        audio_b64 = None
        audio_format = "wav" if active_lang in ["hi", "en"] else "mp3"
        
        wav = self.tts.synthesize(bot_text, active_lang)
        if wav:
            audio_b64 = base64.b64encode(wav).decode()

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
            audio_format = audio_format,
            latency_s    = round(time.time() - t0, 2),
            turn         = session.turn_count,
            llm_model    = self.llm.active_model or "unavailable",
        )
        print("\033[92m[✔] Pipeline Complete\033[0m\n")
        return result
