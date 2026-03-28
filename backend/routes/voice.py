"""
backend/routes/voice.py
------------------------
Flask blueprint for voice and text query endpoints.

Routes:
  POST /api/query        — audio file  → full pipeline response
  POST /api/query_text   — JSON text   → full pipeline response
  POST /api/reset        — reset session (New Customer button)

All business logic lives in VoicePipeline — routes are thin.
"""

import uuid
import logging
from flask import Blueprint, request, jsonify, current_app

log = logging.getLogger("bankbot.routes.voice")

voice_bp = Blueprint("voice", __name__)


def _get_pipeline():
    return current_app.config["BANKBOT_CFG"]._pipeline


def _get_sessions():
    return current_app.config["BANKBOT_CFG"]._sessions


# ── POST /api/query  (audio) ──────────────────────────────────

@voice_bp.route("/query", methods=["POST"])
def query_audio():
    """
    Accepts a raw audio file from the browser microphone.
    Runs the full STT → RAG → LLM → TTS pipeline.
    Returns JSON with bot_text, audio_b64 (WAV), confidence scores.
    """
    sid = request.form.get("session_id") or str(uuid.uuid4())

    if "audio" not in request.files:
        return jsonify({"error": "No audio file in request"}), 400

    audio_bytes = request.files["audio"].read()

    if len(audio_bytes) < 200:
        # Browser sometimes sends empty chunk before mic starts
        return jsonify({"status": "no_speech", "session_id": sid})

    lang_override = request.form.get("language", "auto")

    try:
        result = _get_pipeline().process_audio(audio_bytes, sid, target_lang=lang_override)
    except Exception as e:
        log.error("Pipeline error (audio): %s", e, exc_info=True)
        return jsonify({"error": "Pipeline failed", "detail": str(e)}), 500

    if result.action == "no_speech":
        return jsonify({"status": "no_speech", "session_id": sid})

    return jsonify(result.to_dict())


# ── POST /api/query_text  (text / sample tiles) ───────────────

@voice_bp.route("/query_text", methods=["POST"])
def query_text():
    """
    Accepts a plain-text query (used by sample query tiles and
    keyboard fallback). Skips STT, runs RAG → LLM → TTS.
    """
    body      = request.get_json(force=True) or {}
    sid       = body.get("session_id") or str(uuid.uuid4())
    user_text = (body.get("text") or "").strip()

    if not user_text:
        return jsonify({"error": "Empty text"}), 400

    lang_override = body.get("language", "auto")

    try:
        result = _get_pipeline().process_text(user_text, sid, target_lang=lang_override)
    except Exception as e:
        log.error("Pipeline error (text): %s", e, exc_info=True)
        return jsonify({"error": "Pipeline failed", "detail": str(e)}), 500

    return jsonify(result.to_dict())


# ── POST /api/feedback ────────────────────────────────────────

@voice_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    """
    Accept like/dislike feedback on a bot response.
    On 'like': add query→response to fast-path cache for future instant answers.
    On 'dislike': log only, do not cache.
    """
    from backend.pipeline import FAST_PATH_CACHE, FAST_PATH_KEYWORDS
    body = request.get_json(force=True) or {}
    user_text = (body.get("user_text") or "").strip()
    bot_text  = (body.get("bot_text") or "").strip()
    feedback  = body.get("feedback", "")  # "like" or "dislike"
    lang      = body.get("lang", "en")

    if not user_text or not bot_text or feedback not in ("like", "dislike"):
        return jsonify({"error": "Invalid feedback payload"}), 400

    if feedback == "like":
        # Create a cache key from the user query (lowercase, stripped)
        cache_key = user_text.lower().strip(" .,?!;:'\"")
        # Add to in-memory fast-path cache
        if cache_key not in FAST_PATH_CACHE:
            FAST_PATH_CACHE[cache_key] = {}
        FAST_PATH_CACHE[cache_key][lang] = bot_text
        # Also add strong keywords so it can be fuzzy-matched
        words = [w for w in cache_key.split() if len(w) > 2]
        # Use a 3-word phrase as a strong keyword
        if len(words) >= 3:
            phrase = " ".join(words[:4])
            FAST_PATH_KEYWORDS[cache_key] = {"strong": [phrase, cache_key], "weak": []}
        else:
            FAST_PATH_KEYWORDS[cache_key] = {"strong": [cache_key], "weak": []}
        log.info("📌 Cache updated from user feedback: '%s' -> '%s'", cache_key[:40], bot_text[:60])
        print(f"\033[92m[FEEDBACK] ✅ Liked & Cached: '{cache_key[:40]}'\033[0m")
    else:
        log.info("👎 Disliked response for: '%s'", user_text[:40])
        print(f"\033[91m[FEEDBACK] 👎 Disliked: '{user_text[:40]}'\033[0m")

    return jsonify({"status": "ok", "feedback": feedback})


# ── POST /api/reset ───────────────────────────────────────────

@voice_bp.route("/reset", methods=["POST"])
def reset_session():
    """
    Wipe session history for a given session_id.
    Called when the operator presses "New Customer".
    """
    body = request.get_json(force=True) or {}
    sid  = body.get("session_id")
    if sid:
        _get_sessions().reset(sid)
        log.info("Session reset: %s", sid[:8])
    return jsonify({"status": "reset", "session_id": sid})
