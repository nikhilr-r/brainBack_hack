"""
config/prompts.py
-----------------
All LLM system prompts and response templates.
Centralised so non-engineers can edit tone/language without
touching application logic.
"""

SYSTEM_PROMPT = """You are BankBot, a voice assistant at Nexus Bank. The CONTEXT below is the ONLY information you have. Answer DIRECTLY and ONLY about what the user asked. Be concise (1-2 sentences). No bullet points. {language_rule}

CONTEXT: {context}"""

# Fallback messages when confidence is too low
FALLBACK_MESSAGES = {
    "hi": (
        "माफ़ कीजिए, मैं यह पूरी तरह समझ नहीं पाया। "
        "हमारे टेलर आपकी मदद करेंगे। कृपया काउंटर पर जाएं।"
    ),
    "en": (
        "I'm sorry, I couldn't understand that well enough. "
        "Please speak to our teller at the counter."
    ),
}

# TTS greeting played on session start
GREETING = {
    "hi": "नमस्ते! बैंकबॉट में आपका स्वागत है। आप अपना सवाल पूछ सकते हैं।",
    "en": "Hello! Welcome to BankBot. Please speak your banking question.",
}

# Message when Ollama model is not available
LLM_UNAVAILABLE = {
    "hi": "खेद है, AI सेवा अभी उपलब्ध नहीं है। कृपया टेलर से मिलें।",
    "en": "AI service is currently unavailable. Please speak to our teller.",
}
