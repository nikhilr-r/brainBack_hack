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
  sessionId: crypto.randomUUID(),
  recording: false,
  processing: false,
  stream: null,
  recorder: null,
  chunks: [],
  audioCtx: null,
  analyser: null,
  rafId: null,
  turns: 0,
  langOverride: "auto",
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
      b.style.height = 4 + (v / 255) * 42 + "px";
    });
  }

  function reset() {
    bars.forEach((b) => {
      b.style.height = "4px";
    });
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
          sampleRate: 48000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (e) {
      UI.setLabel("❌ Microphone access denied", "error");
      return;
    }

    STATE.chunks = [];

    // Pick best supported MIME type
    const mime = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg",
      "audio/mp4",
      "",
    ].find((t) => !t || MediaRecorder.isTypeSupported(t));

    STATE.recorder = new MediaRecorder(
      STATE.stream,
      mime ? { mimeType: mime } : {},
    );
    STATE.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) STATE.chunks.push(e.data);
    };
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
    STATE.stream.getTracks().forEach((t) => t.stop());
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
    const blob = new Blob(STATE.chunks, {
      type: STATE.recorder.mimeType || "audio/webm",
    });
    const fd = new FormData();
    fd.append("audio", blob, "query.webm");
    fd.append("session_id", STATE.sessionId);
    fd.append("language", STATE.langOverride);

    UI.showThinking(true);
    try {
      const res = await fetch("/api/query", { method: "POST", body: fd });
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
      const res = await fetch("/api/query_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          session_id: STATE.sessionId,
          language: STATE.langOverride,
        }),
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
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: STATE.sessionId }),
      });
    } catch (_) {}
  }

  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      StatusBar.update(data);
    } catch (_) {}
  }

  async function sendFeedback(userText, botText, feedback, lang) {
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_text: userText,
          bot_text: botText,
          feedback: feedback,
          lang: lang || "en",
        }),
      });
    } catch (err) {
      console.error("Feedback error:", err);
    }
  }

  return { sendAudio, sendText, resetSession, fetchStatus, sendFeedback };
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
      turns: STATE.turns,
      conf: Math.round((data.confidence?.overall || 0) * 100) + "%",
      lang: data.lang === "hi" ? "हिंदी" : "English",
      latency: (data.latency_s || 0).toFixed(1) + "s",
    });

    // Remove hard-coded language badge update, as the user manually toggles it now.
    // document.getElementById("lang-badge").textContent =
    //   data.lang === "hi" ? "🇮🇳 हिंदी" : "🇬🇧 English";

    // Add conversation messages
    UI.addMessage("user", data.user_text, null, false);
    UI.addMessage(
      "bot",
      data.bot_text,
      data.confidence,
      data.action === "teller_alert",
    );

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
      const fmt = data.audio_format || "wav";
      const player = document.getElementById("audio-player");
      player.src = `data:audio/${fmt};base64,${data.audio_b64}`;
      player.play().catch(() => {}); // autoplay may be blocked — silent fail
    } else if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(data.bot_text);
      const targetLang = data.lang === "hi" ? "hi" : "en";
      utterance.lang = targetLang === "hi" ? "hi-IN" : "en-IN";
      utterance.rate = 0.95;

      // Try to find the best matching voice for the language
      const voices = window.speechSynthesis.getVoices();
      const matchVoice = voices.find((v) => v.lang.startsWith(targetLang));
      if (matchVoice) utterance.voice = matchVoice;

      window.speechSynthesis.speak(utterance);
    } else {
      showPromptLater();
    }

    // Update debug panel
    document.getElementById("debug-panel").textContent = JSON.stringify(
      {
        user_text: data.user_text,
        bot_text: data.bot_text,
        lang: data.lang,
        confidence: data.confidence,
        action: data.action,
        llm_model: data.llm_model,
        latency_s: data.latency_s,
        ctx_preview: (data.context_used || "").slice(0, 250) + "…",
      },
      null,
      2,
    );
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
      
      // Update RAG Visualizer Panel
      updateRAGVisualizer(text, conf, pct);
    }

    // Feedback buttons for bot messages
    let feedbackHTML = "";
    if (role === "bot" && !isFallback) {
      const msgId = "fb-" + Date.now() + "-" + Math.random().toString(36).substr(2, 5);
      feedbackHTML = `
        <div class="feedback-row" id="${msgId}">
          <button class="fb-btn fb-like" data-feedback="like" title="Good answer — cache this">
            <span class="fb-icon">👍</span>
          </button>
          <button class="fb-btn fb-dislike" data-feedback="dislike" title="Bad answer">
            <span class="fb-icon">👎</span>
          </button>
        </div>`;
    }

    wrap.innerHTML = `
      <div class="avatar">${role === "user" ? "👤" : "🤖"}</div>
      <div>
        <div class="bubble">${escHtml(text)}</div>
        ${metaHTML}
        ${feedbackHTML}
      </div>`;

    convo.appendChild(wrap);
    convo.scrollTop = convo.scrollHeight;

    // Update Dashboard Live Transcript Feed
    updateDashboardFeed(role, text);
  }

  function showThinking(visible) {
    const el = document.getElementById("thinking-wrap");
    el.classList.toggle("visible", visible);
    const convo = document.getElementById("conversation");
    convo.scrollTop = convo.scrollHeight;
  }

  function showTellerAlert(msg) {
    const el = document.getElementById("teller-alert");
    const body = document.getElementById("teller-msg");
    body.textContent = msg;
    el.classList.add("visible");
    setTimeout(() => el.classList.remove("visible"), 14000);
  }

  function setRecordingState(recording) {
    const btn = document.getElementById("mic-btn");
    btn.classList.toggle("recording", recording);
    ["mic-ring-1", "mic-ring-2", "mic-ring-3"].forEach((id) => {
      document.getElementById(id).classList.toggle("off", !recording);
    });
  }

  function setProcessing(processing) {
    STATE.processing = processing;
    const btn = document.getElementById("mic-btn");
    btn.classList.toggle("processing", processing);
    btn.disabled = processing;
    btn.textContent = processing ? "⏳" : "🎙️";

    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    if (chatInput) chatInput.disabled = processing;
    if (sendBtn) sendBtn.disabled = processing;
  }

  function setLabel(html, type) {
    const el = document.getElementById("mic-label");
    el.innerHTML = html;
    el.className = `mic-label${type ? " " + type : ""}`;
  }

  function updateStats({ turns, conf, lang, latency }) {
    document.getElementById("stat-turns").textContent = turns;
    document.getElementById("stat-conf").textContent = conf;
    document.getElementById("stat-lang").textContent = lang;
    document.getElementById("stat-latency").textContent = latency;
  }

  return {
    addMessage,
    showThinking,
    showTellerAlert,
    setRecordingState,
    setProcessing,
    setLabel,
    updateStats,
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
      data.fully_offline
        ? tag("🔒 FULLY OFFLINE", true)
        : tag("⚠ LLM missing", false),
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
  
  const modes = [
    { id: "auto", label: "🌐 Auto-Detect" },
    { id: "hi",   label: "🇮🇳 Hindi Only" },
    { id: "en",   label: "🇬🇧 English Only" }
  ];
  const selectedMode = modes.find(m => m.id === lang) || modes[0];
  document.getElementById("lang-badge").textContent = selectedMode.label;
  
  // Optional: prompt the user to speak
  UI.addMessage("bot", lang === 'hi' ? "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?" : "Hello! How can I help you?", null, false);
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

window.toggleLanguageOverride = function () {
  const modes = [
    { id: "auto", label: "🌐 Auto-Detect" },
    { id: "hi", label: "🇮🇳 Hindi Only" },
    { id: "en", label: "🇬🇧 English Only" },
  ];
  let currIdx = modes.findIndex((m) => m.id === STATE.langOverride);
  let nextIdx = (currIdx + 1) % modes.length;
  STATE.langOverride = modes[nextIdx].id;
  document.getElementById("lang-badge").textContent = modes[nextIdx].label;
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
   9. SPA VIEW TOGGLING & DASHBOARD LOGIC
   ───────────────────────────────────────────────────────────── */

// Safe HTML escaping for global scope (UI.escHtml is only in its closure)
function _esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

window.switchView = function(viewId) {
  document.querySelectorAll(".view").forEach(el => el.classList.remove("active"));
  document.getElementById(viewId).classList.add("active");

  document.querySelectorAll(".nav-btn").forEach(el => el.classList.remove("active"));
  const btnId = "nav-" + viewId.replace("-view", "");
  const btn = document.getElementById(btnId);
  if (btn) btn.classList.add("active");
};

window.updateRAGVisualizer = function(replyText, conf, pctScore) {
  const panel = document.getElementById("rag-visualizer");
  if (!panel) return;

  const empty = panel.querySelector(".rag-empty");
  if (empty) empty.remove();

  const similarity = conf && conf.rag ? (conf.rag * 100).toFixed(1) : "0.0";
  const chunkText = replyText.substring(0, 150) + "...";
  
  const chunkHtml = `
    <div class="chunk-card">
      <div class="chunk-header">
        <span class="chunk-lbl">RAG NODE HIT</span>
        <span class="chunk-score">SIMILARITY: ${similarity}%</span>
      </div>
      <div class="chunk-text">${_esc(chunkText)}</div>
    </div>
  `;
  panel.insertAdjacentHTML('afterbegin', chunkHtml);
};

window.updateDashboardFeed = function(role, text) {
  const feed = document.getElementById("dash-transcript");
  if (!feed) return;

  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const roleLabel = role === 'user' ? `<span class="dash-log-user">[USER]</span>` : `<span class="dash-log-bot">[BRAINBACK.AI]</span>`;
  
  const logHtml = `
    <div class="dash-log">
      <span class="dash-log-time">${time}</span> ${roleLabel} <span>${_esc(text)}</span>
    </div>
  `;
  feed.insertAdjacentHTML('beforeend', logHtml);
  feed.scrollTop = feed.scrollHeight;
};

// Simple hardware proxy loop
setInterval(() => {
  const cpu = document.querySelector('.hw-fill.cpu');
  const ram = document.querySelector('.hw-fill.ram');
  if (cpu && ram) {
    const baseCpu = STATE.processing ? 85 : 10;
    cpu.style.width = (baseCpu + Math.floor(Math.random() * 15)) + '%';
    ram.style.width = (65 + Math.floor(Math.random() * 5)) + '%';
  }
}, 2000);

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
  // ── Feedback button handler ─────────────────────────────
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".fb-btn");
    if (!btn) return;
    const row = btn.closest(".feedback-row");
    if (!row || row.dataset.sent) return;

    const feedback = btn.dataset.feedback;
    const msgWrap = btn.closest(".msg");
    const bubble = msgWrap.querySelector(".bubble");
    const botText = bubble ? bubble.textContent : "";

    // Find the preceding user message
    const allMsgs = Array.from(document.querySelectorAll(".msg"));
    const idx = allMsgs.indexOf(msgWrap);
    let userText = "";
    for (let i = idx - 1; i >= 0; i--) {
      if (allMsgs[i].classList.contains("user")) {
        const ub = allMsgs[i].querySelector(".bubble");
        userText = ub ? ub.textContent : "";
        break;
      }
    }

    API.sendFeedback(userText, botText, feedback, STATE.langOverride);
    row.dataset.sent = "1";
    row.innerHTML = feedback === "like"
      ? '<span class="fb-done fb-done-like">✅ Cached for future use!</span>'
      : '<span class="fb-done fb-done-dislike">Noted, thanks for feedback</span>';
  });
});
