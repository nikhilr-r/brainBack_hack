/**
 * BrainBack.AI — BankBot Kiosk Frontend
 * frontend/static/js/app.js
 *
 * Organised into logical sections:
 *   1. State
 *   2. Waveform visualiser
 *   3. Microphone recording
 *   4. API communication
 *   5. Response handling
 *   6. DOM helpers (messages, labels, stats)
 *   7. Status polling
 *   8. Init
 */

"use strict";

/* ─────────────────────────────────────────────────────────────
   1. STATE
   ───────────────────────────────────────────────────────────── */
const STATE = {
  sessionId:   crypto.randomUUID(),
  recording:   false,
  processing:  false,
  stream:      null,
  recorder:    null,
  chunks:      [],
  audioCtx:    null,
  analyser:    null,
  rafId:       null,
  turns:       0,
  langOverride:"auto",
  exitPromptTimer: null,
};


/* ─────────────────────────────────────────────────────────────
   2. WAVEFORM VISUALISER
   ───────────────────────────────────────────────────────────── */
const Visualiser = (() => {
  const NUM_BARS = 36;
  let bars = [];

  function init() {
    const waveEl = document.getElementById("waveform");
    for (let i = 0; i < NUM_BARS; i++) {
      const b = document.createElement("div");
      b.className = "wave-bar";
      waveEl.appendChild(b);
      bars.push(b);
    }
  }

  function drawFromArray(dataArray) {
    const step = Math.floor(dataArray.length / NUM_BARS);
    bars.forEach((b, i) => {
      const v = dataArray[i * step] || 0;
      b.style.height = (4 + (v / 255) * 42) + "px";
    });
  }

  function reset() {
    bars.forEach(b => { b.style.height = "4px"; });
  }

  function start(stream) {
    if (!STATE.audioCtx) {
      STATE.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    STATE.analyser = STATE.audioCtx.createAnalyser();
    STATE.analyser.fftSize = 256;
    STATE.audioCtx.createMediaStreamSource(stream).connect(STATE.analyser);

    const data = new Uint8Array(STATE.analyser.frequencyBinCount);
    const loop = () => {
      STATE.rafId = requestAnimationFrame(loop);
      STATE.analyser.getByteFrequencyData(data);
      drawFromArray(data);
    };
    loop();
    document.getElementById("waveform").classList.add("active");
  }

  function stop() {
    if (STATE.rafId) cancelAnimationFrame(STATE.rafId);
    reset();
    document.getElementById("waveform").classList.remove("active");
  }

  return { init, start, stop };
})();


/* ─────────────────────────────────────────────────────────────
   3. MICROPHONE RECORDING
   ───────────────────────────────────────────────────────────── */
const Recorder = (() => {

  async function start() {
    try {
      STATE.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate:        48000,
          channelCount:      1,
          echoCancellation:  true,
          noiseSuppression:  true,
          autoGainControl:   true,
        },
      });
    } catch (e) {
      UI.setLabel("❌ Microphone access denied", "error");
      return;
    }

    STATE.chunks = [];

    // Pick best supported MIME type
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/mp4", ""]
      .find(t => !t || MediaRecorder.isTypeSupported(t));

    STATE.recorder = new MediaRecorder(STATE.stream, mime ? { mimeType: mime } : {});
    STATE.recorder.ondataavailable = e => { if (e.data.size > 0) STATE.chunks.push(e.data); };
    STATE.recorder.onstop = API.sendAudio;
    STATE.recorder.start(100);

    STATE.recording = true;
    UI.setRecordingState(true);
    Visualiser.start(STATE.stream);
    UI.setLabel("🔴 Recording… tap to stop", "active");
    document.getElementById("teller-alert").classList.remove("visible");
  }

  function stop() {
    if (!STATE.recorder) return;
    STATE.recorder.stop();
    STATE.stream.getTracks().forEach(t => t.stop());
    STATE.recording = false;
    Visualiser.stop();
    UI.setRecordingState(false);
    UI.setLabel("⏳ Processing…", "active");
    UI.setProcessing(true);
  }

  return { start, stop };
})();


/* ─────────────────────────────────────────────────────────────
   4. API COMMUNICATION
   ───────────────────────────────────────────────────────────── */
const API = (() => {

  async function sendAudio() {
    const blob = new Blob(STATE.chunks, { type: STATE.recorder.mimeType || "audio/webm" });
    const fd   = new FormData();
    fd.append("audio",      blob, "query.webm");
    fd.append("session_id", STATE.sessionId);
    fd.append("language",   STATE.langOverride);

    UI.showThinking(true);
    try {
      const res  = await fetch("/api/query", { method: "POST", body: fd });
      const data = await res.json();
      UI.showThinking(false);
      ResponseHandler.handle(data);
    } catch (err) {
      UI.showThinking(false);
      UI.setLabel("❌ Server error — please try again", "error");
      UI.setProcessing(false);
      console.error("Audio query error:", err);
    }
  }

  async function sendText(text) {
    UI.showThinking(true);
    try {
      const res  = await fetch("/api/query_text", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ text, session_id: STATE.sessionId, language: STATE.langOverride }),
      });
      const data = await res.json();
      UI.showThinking(false);
      ResponseHandler.handle(data);
    } catch (err) {
      UI.showThinking(false);
      UI.setLabel("❌ Server error", "error");
      console.error("Text query error:", err);
    }
  }

  async function resetSession() {
    try {
      await fetch("/api/reset", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ session_id: STATE.sessionId }),
      });
    } catch (_) {}
  }

  async function fetchStatus() {
    try {
      const res  = await fetch("/api/status");
      const data = await res.json();
      StatusBar.update(data);
    } catch (_) {}
  }

  return { sendAudio, sendText, resetSession, fetchStatus };
})();


/* ─────────────────────────────────────────────────────────────
   5. RESPONSE HANDLING
   ───────────────────────────────────────────────────────────── */
const ResponseHandler = (() => {

  function handle(data) {
    UI.setProcessing(false);
    UI.setLabel("Tap to speak &nbsp;•&nbsp; बोलने के लिए टैप करें", "");

    if (data.status === "no_speech") {
      UI.setLabel("🔇 No speech detected — please try again", "error");
      return;
    }
    if (data.error) {
      UI.setLabel("❌ " + data.error, "error");
      return;
    }

    // Update stats
    STATE.turns = data.turn || STATE.turns + 1;
    UI.updateStats({
      turns:   STATE.turns,
      conf:    Math.round((data.confidence?.overall || 0) * 100) + "%",
      lang:    data.lang === "hi" ? "हिंदी" : "English",
      latency: (data.latency_s || 0).toFixed(1) + "s",
    });

    // Remove hard-coded language badge update, as the user manually toggles it now.
    // document.getElementById("lang-badge").textContent =
    //   data.lang === "hi" ? "🇮🇳 हिंदी" : "🇬🇧 English";

    // Add conversation messages
    UI.addMessage("user", data.user_text, null, false);
    UI.addMessage("bot",  data.bot_text, data.confidence, data.action === "teller_alert");

    // Teller alert
    if (data.action === "teller_alert") {
      UI.showTellerAlert(data.bot_text);
    }

    const showPromptLater = () => {
      if (data.action !== "teller_alert" && data.action !== "no_speech") {
        clearTimeout(STATE.exitPromptTimer);
        STATE.exitPromptTimer = setTimeout(() => {
          document.getElementById('exit-prompt').classList.add('visible');
        }, 5000);
      }
    };

    // Play TTS audio
    if (data.audio_b64) {
      const fmt    = data.audio_format || "wav";
      const player = document.getElementById("audio-player");
      player.src   = `data:audio/${fmt};base64,${data.audio_b64}`;
      player.onended = showPromptLater;
      player.play().catch(() => { showPromptLater(); });  // autoplay may be blocked — silent fail
    } else if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(data.bot_text);
      const bcpMap = {
        "en": "en-IN", "hi": "hi-IN", "mr": "mr-IN", "gu": "gu-IN", 
        "bn": "bn-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN", 
        "ml": "ml-IN", "pa": "pa-IN", "or": "or-IN", "as": "as-IN"
      };
      const targetLang = data.lang;
      utterance.lang = bcpMap[data.lang] || "en-IN";
      utterance.rate = 0.95;
      
      // Try to find the best matching voice for the language
      const voices = window.speechSynthesis.getVoices();
      const matchVoice = voices.find(v => v.lang.startsWith(targetLang));
      
      if (matchVoice) {
        utterance.voice = matchVoice;
        utterance.onend = showPromptLater;
        utterance.onerror = showPromptLater;
        window.speechSynthesis.speak(utterance);
      } else {
        // Fallback to Cloud TTS for regional Indian languages if no native Windows voice is installed
        console.warn("No offline voice found for", targetLang, "— falling back to Cloud TTS");
        const fallbackAudio = new Audio(`https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=${targetLang}&q=${encodeURIComponent(data.bot_text)}`);
        fallbackAudio.onended = showPromptLater;
        fallbackAudio.onerror = showPromptLater;
        fallbackAudio.play().catch(() => showPromptLater());
      }
    } else {
      showPromptLater();
    }

    // Update debug panel
    document.getElementById("debug-panel").textContent = JSON.stringify({
      user_text:    data.user_text,
      bot_text:     data.bot_text,
      lang:         data.lang,
      confidence:   data.confidence,
      action:       data.action,
      llm_model:    data.llm_model,
      latency_s:    data.latency_s,
      ctx_preview:  (data.context_used || "").slice(0, 250) + "…",
    }, null, 2);
  }

  return { handle };
})();


/* ─────────────────────────────────────────────────────────────
   6. DOM HELPERS
   ───────────────────────────────────────────────────────────── */
const UI = (() => {

  function escHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function removeEmptyState() {
    const el = document.getElementById("empty-state");
    if (el) el.remove();
  }

  function addMessage(role, text, conf, isFallback) {
    removeEmptyState();
    const convo = document.getElementById("conversation");

    const wrap = document.createElement("div");
    wrap.className = `msg ${role}${isFallback ? " fallback" : ""}`;

    let metaHTML = "";
    if (role === "bot" && conf) {
      const pct = Math.round(conf.overall * 100);
      const cls = pct >= 60 ? "conf-hi" : pct >= 38 ? "conf-med" : "conf-lo";
      metaHTML = `
        <div class="msg-meta">
          <span class="conf-badge ${cls}">${pct}% conf</span>
          <span>STT ${Math.round(conf.stt * 100)}%</span>
          <span>RAG ${Math.round(conf.rag * 100)}%</span>
        </div>`;
    }

    wrap.innerHTML = `
      <div class="avatar">${role === "user" ? "👤" : "🤖"}</div>
      <div>
        <div class="bubble">${escHtml(text)}</div>
        ${metaHTML}
      </div>`;

    convo.appendChild(wrap);
    convo.scrollTop = convo.scrollHeight;
  }

  function showThinking(visible) {
    const el = document.getElementById("thinking-wrap");
    el.classList.toggle("visible", visible);
    const convo = document.getElementById("conversation");
    convo.scrollTop = convo.scrollHeight;
  }

  function showTellerAlert(msg) {
    const el   = document.getElementById("teller-alert");
    const body = document.getElementById("teller-msg");
    body.textContent = msg;
    el.classList.add("visible");
    setTimeout(() => el.classList.remove("visible"), 14000);
  }

  function setRecordingState(recording) {
    const btn = document.getElementById("mic-btn");
    btn.classList.toggle("recording", recording);
    ["mic-ring-1", "mic-ring-2", "mic-ring-3"].forEach(id => {
      document.getElementById(id).classList.toggle("off", !recording);
    });
  }

  function setProcessing(processing) {
    STATE.processing = processing;
    const btn = document.getElementById("mic-btn");
    btn.classList.toggle("processing", processing);
    btn.disabled   = processing;
    btn.textContent = processing ? "⏳" : "🎙️";

    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    if (chatInput) chatInput.disabled = processing;
    if (sendBtn) sendBtn.disabled = processing;
  }

  function setLabel(html, type) {
    const el = document.getElementById("mic-label");
    el.innerHTML   = html;
    el.className   = `mic-label${type ? " " + type : ""}`;
  }

  function updateStats({ turns, conf, lang, latency }) {
    document.getElementById("stat-turns").textContent   = turns;
    document.getElementById("stat-conf").textContent    = conf;
    document.getElementById("stat-lang").textContent    = lang;
    document.getElementById("stat-latency").textContent = latency;
  }

  return {
    addMessage, showThinking, showTellerAlert,
    setRecordingState, setProcessing, setLabel, updateStats,
  };
})();


/* ─────────────────────────────────────────────────────────────
   7. STATUS BAR POLLING
   ───────────────────────────────────────────────────────────── */
const StatusBar = (() => {
  function update(data) {
    const row = document.getElementById("model-bar");
    if (!row) return;

    const tag = (label, on) =>
      `<span class="model-tag ${on ? "mt-on" : "mt-off"}">${label}</span>`;
    const sep = `<span class="mt-sep">|</span>`;

    const llmOk = data.models?.llm && data.models.llm !== "not loaded";

    row.innerHTML = [
      `<span class="mt-lbl">STT:</span> ${tag("Whisper " + (data.models?.stt?.split("/")[1] || ""), true)}`,
      sep,
      `<span class="mt-lbl">LLM:</span> ${tag(data.models?.llm || "Not loaded", llmOk)}`,
      sep,
      `<span class="mt-lbl">TTS:</span> ${tag("pyttsx3", true)}`,
      sep,
      `<span class="mt-lbl">KB:</span>  ${tag(data.kb_entries + " FAQs", true)}`,
      sep,
      data.fully_offline ? tag("🔒 FULLY OFFLINE", true) : tag("⚠ LLM missing", false),
    ].join(" ");
  }

  function startPolling() {
    API.fetchStatus();
    setInterval(API.fetchStatus, 8000);
  }

  return { update, startPolling };
})();


/* ─────────────────────────────────────────────────────────────
   8. PUBLIC EVENT HANDLERS (called from HTML onclick)
   ───────────────────────────────────────────────────────────── */

window.startSession = function(lang) {
  STATE.sessionId = crypto.randomUUID();
  STATE.langOverride = lang;
  STATE.turns = 0;
  
  document.getElementById('welcome-overlay').style.display = 'none';
  document.getElementById('main-ui').style.display = 'flex';
  
  const badgeMap = {
    "en": "🌐 English", "hi": "🌐 हिंदी", "mr": "🌐 मराठी", "gu": "🌐 ગુજરાતી",
    "bn": "🌐 বাংলা", "ta": "🌐 தமிழ்", "te": "🌐 తెలుగు", "kn": "🌐 ಕನ್ನಡ",
    "ml": "🌐 മലയാളം", "pa": "🌐 ਪੰਜਾਬੀ", "or": "🌐 ଓଡ଼ିଆ", "as": "🌐 অসমীয়া"
  };
  document.getElementById("lang-badge").textContent = badgeMap[lang] || "🌐 English";
  
  const greetings = {
    "en": "Hello! How can I help you?", "hi": "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
    "mr": "नमस्कार! मी तुम्हाला कशी मदत करू शकतो?", "gu": "નમસ્તે! હું તમને કેવી રીતે મદદ કરી શકું?",
    "bn": "নমস্কার! আমি আপনাকে কীভাবে সাহায্য করতে পারি?", "ta": "வணக்கம்! நான் உங்களுக்கு எப்படி உதவ முடியும்?",
    "te": "నమస్కారం! నేను మీకు ఎలా సహాయపడగలను?", "kn": "ನಮಸ್ಕಾರ! ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ?",
    "ml": "നമസ്കാരം! നിങ്ങളെ എങ്ങനെ സഹായിക്കാനാകും?", "pa": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?",
    "or": "ନମସ୍କାର! ମୁଁ ଆପଣଙ୍କୁ କିପରି ସାହାଯ্য କରିପାରିବି?", "as": "নমস্কাৰ! মই আপোনাক কেনেকৈ সহায় কৰিব পাৰোঁ?"
  };
  UI.addMessage("bot", greetings[lang] || greetings["en"], null, false);
};

window.endSession = async function() {
  await window.resetSession();
};

window.hideExitPrompt = function() {
  document.getElementById('exit-prompt').classList.remove('visible');
  clearTimeout(STATE.exitPromptTimer);
};

window.toggleMic = function () {
  if (STATE.processing) return;
  window.hideExitPrompt();
  STATE.recording ? Recorder.stop() : Recorder.start();
};

window.askSample = function (text) {
  window.hideExitPrompt();
  // Show user message immediately, then query
  UI.addMessage("user", text, null, false);
  API.sendText(text);
};

window.submitTextQuery = function () {
  if (STATE.processing) return;
  const inputEl = document.getElementById("chat-input");
  const text = inputEl.value.trim();
  if (!text) return;

  window.hideExitPrompt();
  inputEl.value = "";
  // Show user message immediately, then query
  UI.addMessage("user", text, null, false);
  API.sendText(text);
};

window.resetSession = async function () {
  await API.resetSession();
  location.reload();
};

window.toggleDebug = function () {
  document.getElementById("debug-panel").classList.toggle("visible");
};


/* ─────────────────────────────────────────────────────────────
   INIT — runs on DOMContentLoaded
   ───────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  Visualiser.init();
  StatusBar.startPolling();

  const chatInput = document.getElementById("chat-input");
  if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        window.submitTextQuery();
      }
    });
  }

  const sendBtn = document.getElementById("send-btn");
  if (sendBtn) {
    sendBtn.addEventListener("click", window.submitTextQuery);
  }
});
