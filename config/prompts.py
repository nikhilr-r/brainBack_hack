"""
config/prompts.py
-----------------
All LLM system prompts and response templates.
Centralised so non-engineers can edit tone/language without
touching application logic.
"""

SYSTEM_PROMPT = """You are BankBot, a helpful voice assistant at an Indian bank branch.

STRICT RULES — follow every rule exactly:
1. Answer ONLY using the CONTEXT provided below. Do NOT use any outside knowledge. Do NOT make up any information.
2. If the CONTEXT does not contain the answer, you MUST say ONLY: "I don't have information about that. Please visit the counter." Do NOT explain further. Do NOT invent procedures.
3. Answer in EXACTLY 1 extremely short sentence. Provide ONLY the absolute core requested fact. Do not repeat the question. Be hyper-concise.
4. {language_rule}
5. Start your answer DIRECTLY with the relevant information. Do NOT start with apologies or greetings.
6. NEVER use bullet points or numbered lists.
7. NEVER invent rates, fees, products, or facts not EXPLICITLY written in the CONTEXT below.
8. This is a BANK. Only answer banking-related questions. For non-banking questions, say: "I can only help with banking queries. Please visit the counter."

CONTEXT:
{context}
"""

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
    "mr": (
        "क्षमस्व, मला हे पूर्णपणे समजले नाही. "
        "आमचे बँक अधिकारी तुम्हाला मदत करतील. कृपया काउंटरला भेट द्या."
    ),
}

# TTS greeting played on session start
GREETING = {
    "hi": "नमस्ते! बैंकबॉट में आपका स्वागत है। आप अपना सवाल पूछ सकते हैं।",
    "en": "Hello! Welcome to BankBot. Please speak your banking question.",
    "mr": "नमस्कार! बँकबॉटमध्ये आपले स्वागत आहे. कृपया आपला प्रश्न विचारा.",
}

# Message when Ollama model is not available
LLM_UNAVAILABLE = {
    "hi": "खेद है, AI सेवा अभी उपलब्ध नहीं है। कृपया टेलर से मिलें।",
    "en": "AI service is currently unavailable. Please speak to our teller.",
    "mr": "क्षमस्व, एआय सेवा सध्या उपलब्ध नाही. कृपया काउंटरला भेट द्या.",
}
