"""
backend/translate.py
--------------------
Fully OFFLINE translation using argostranslate.

Flow:
    User speaks Hindi → Whisper detects lang="hi"
    LLM generates answer in English (always accurate)
    translate_response(en_text, "hi") → argostranslate → clean Hindi

Language packs are downloaded ONCE on first use and cached locally forever.
No internet is needed after the initial pack download.

Install:
    pip install argostranslate

Supported target_lang codes (Whisper-compatible):
    "en" → English  (no translation needed)
    "hi" → Hindi
    "mr" → Marathi
    "gu" → Gujarati
    "ta" → Tamil
    "te" → Telugu
    "bn" → Bengali
    "pa" → Punjabi

If argostranslate is not installed or the pack is not yet downloaded,
returns the original English text (graceful degradation).
"""

import logging

log = logging.getLogger("bankbot.translate")

# Map Whisper lang codes → ISO 639-1 codes used by argostranslate
_WHISPER_TO_ARGO = {
    "hi": "hi",   # Hindi
    "mr": "mr",   # Marathi
    "gu": "gu",   # Gujarati
    "ta": "ta",   # Tamil
    "te": "te",   # Telugu
    "bn": "bn",   # Bengali
    "pa": "pa",   # Punjabi
    "ur": "ur",   # Urdu
    "en": "en",   # English
    "auto": "en", # Default to English
}

try:
    from argostranslate import package as _argo_pkg
    from argostranslate import translate as _argo_translate
    _ARGO_AVAILABLE = True
    log.info("✅ argostranslate available — fully offline multilingual translation enabled")
except ImportError:
    _ARGO_AVAILABLE = False
    log.warning(
        "⚠ argostranslate not installed — responses will be in English only.\n"
        "  Run: pip install argostranslate"
    )

# Track which language packs have already been ensured this session
_packs_loaded: set = set()


def _ensure_pack(src: str, tgt: str) -> bool:
    """
    Check if the argostranslate language pack for src→tgt is installed.
    If not, download and install it automatically (requires internet once).

    Returns True if the pack is ready, False otherwise.
    """
    key = f"{src}-{tgt}"
    if key in _packs_loaded:
        return True

    try:
        # Check if pack already installed
        installed = _argo_translate.get_installed_languages()
        installed_codes = {lang.code for lang in installed}

        if src in installed_codes and tgt in installed_codes:
            _packs_loaded.add(key)
            return True

        # Pack not installed — attempt one-time download
        log.info("[TRANSLATE] Pack %s→%s not found, downloading...", src, tgt)
        print(f"\033[93m    [TRANSLATE] Downloading language pack {src}→{tgt} (one-time only)...\033[0m")
        _argo_pkg.update_package_index()
        available = _argo_pkg.get_available_packages()
        target_pkg = next(
            (p for p in available if p.from_code == src and p.to_code == tgt),
            None,
        )
        if target_pkg:
            _argo_pkg.install_from_path(target_pkg.download())
            _packs_loaded.add(key)
            log.info("[TRANSLATE] Pack %s→%s installed ✅", src, tgt)
            print(f"\033[92m    [TRANSLATE] Pack {src}→{tgt} ready ✅\033[0m")
            return True
        else:
            log.warning("[TRANSLATE] No pack available for %s→%s", src, tgt)
            return False

    except Exception as e:
        log.warning("[TRANSLATE] Pack setup failed for %s→%s: %s", src, tgt, e)
        return False


def translate_response(text: str, target_lang: str) -> str:
    """
    Translate English text to target_lang using argostranslate (fully offline).

    Args:
        text:        English text from LLM / RAG.
        target_lang: Whisper language code (e.g. "hi", "mr", "en").

    Returns:
        Translated string, or original English text if translation fails.
    """
    argo_lang = _WHISPER_TO_ARGO.get(target_lang, "en")

    # No translation needed for English
    if argo_lang == "en":
        return text

    if not _ARGO_AVAILABLE:
        log.debug("argostranslate not installed — returning English text.")
        return text

    if not _ensure_pack("en", argo_lang):
        log.warning("[TRANSLATE] Pack missing for en→%s — returning English.", argo_lang)
        return text

    try:
        installed = _argo_translate.get_installed_languages()
        src_lang_obj = next((l for l in installed if l.code == "en"), None)
        tgt_lang_obj = next((l for l in installed if l.code == argo_lang), None)

        if not src_lang_obj or not tgt_lang_obj:
            return text

        translation = src_lang_obj.get_translation(tgt_lang_obj)
        if not translation:
            return text

        translated = translation.translate(text)
        log.info("[TRANSLATE] en→%s: '%s…'", argo_lang, translated[:60])
        return translated

    except Exception as e:
        log.warning("[TRANSLATE] Failed (en→%s): %s — returning English.", argo_lang, e)
        return text
