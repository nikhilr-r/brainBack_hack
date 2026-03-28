/**
 * BankBot Widget Loader
 * Injects a floating chat bubble and an iframe for the BankBot.
 * Drop in: <script src="/static/js/widget-loader.js"></script>
 */
(function () {
  "use strict";

  /* --- Config --- */
  const WIDGET_URL = "/widget";
  const BUBBLE_SIZE = 60; // px
  const MARGIN = 24; // px from edge
  const WIDGET_W = 380; // px
  const WIDGET_H_MAX = 600; // px (max, clamped by viewport)

  /* --- Compute safe widget height --- */
  function getWidgetHeight() {
    // Leave room for the bubble + margin + some padding above
    const available = window.innerHeight - BUBBLE_SIZE - MARGIN * 3 - 16;
    return Math.min(WIDGET_H_MAX, Math.max(300, available));
  }

  /* --- Inject CSS --- */
  const style = document.createElement("style");
  style.innerHTML = `
    #bb-bubble {
      position: fixed;
      bottom: ${MARGIN}px;
      right: ${MARGIN}px;
      width: ${BUBBLE_SIZE}px;
      height: ${BUBBLE_SIZE}px;
      border-radius: 50%;
      background: linear-gradient(135deg, #292075, #00B5EF);
      box-shadow: 0 8px 28px rgba(0,181,239,0.45);
      cursor: pointer;
      z-index: 99999;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 26px;
      transition: transform 0.2s, box-shadow 0.2s;
      user-select: none;
    }
    #bb-bubble:hover {
      transform: scale(1.1);
      box-shadow: 0 12px 36px rgba(0,181,239,0.55);
    }
    #bb-bubble.open {
      background: linear-gradient(135deg, #e31e24, #292075);
      transform: rotate(45deg);
    }
    #bb-badge {
      position: absolute;
      top: -4px;
      right: -4px;
      width: 20px;
      height: 20px;
      background: #e31e24;
      border-radius: 50%;
      font-size: 11px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-weight: 700;
      border: 2px solid #fff;
    }
    #bb-container {
      position: fixed;
      right: ${MARGIN}px;
      bottom: ${MARGIN + BUBBLE_SIZE + 12}px;
      width: ${WIDGET_W}px;
      border-radius: 16px;
      box-shadow: 0 16px 56px rgba(0,0,0,0.28);
      overflow: hidden;
      z-index: 99998;
      display: none;
      background: #060E1E;
      border: 1px solid rgba(0,181,239,0.25);
    }
    #bb-container.open {
      display: flex;
      flex-direction: column;
      animation: bb-pop 0.28s cubic-bezier(0.34,1.56,0.64,1);
    }
    #bb-iframe {
      width: 100%;
      border: none;
      flex: 1;
    }
    @keyframes bb-pop {
      from { opacity: 0; transform: translateY(20px) scale(0.92); }
      to   { opacity: 1; transform: translateY(0)   scale(1); }
    }
    @media (max-width: 500px) {
      #bb-container {
        right: 0 !important;
        bottom: ${MARGIN + BUBBLE_SIZE + 8}px !important;
        width: 100vw !important;
        border-radius: 16px 16px 0 0 !important;
      }
    }
  `;
  document.head.appendChild(style);

  /* --- Bubble --- */
  const bubble = document.createElement("div");
  bubble.id = "bb-bubble";
  bubble.title = "Chat with BankBot AI";
  bubble.innerHTML = '🤖<span id="bb-badge">1</span>';
  document.body.appendChild(bubble);

  /* --- Widget container + iframe --- */
  const container = document.createElement("div");
  container.id = "bb-container";

  const iframe = document.createElement("iframe");
  iframe.id = "bb-iframe";
  iframe.src = WIDGET_URL;
  iframe.allow = "microphone"; // ← CRITICAL: allows mic access in iframe

  container.appendChild(iframe);
  document.body.appendChild(container);

  /* --- Set height dynamically --- */
  function updateWidgetHeight() {
    container.style.height = getWidgetHeight() + "px";
    iframe.style.height = getWidgetHeight() + "px";
  }
  updateWidgetHeight();
  window.addEventListener("resize", updateWidgetHeight);

  /* --- Toggle --- */
  let isOpen = false;
  bubble.addEventListener("click", () => {
    isOpen = !isOpen;
    bubble.classList.toggle("open", isOpen);
    container.classList.toggle("open", isOpen);
    // Remove notification badge once opened
    const badge = document.getElementById("bb-badge");
    if (badge && isOpen) badge.style.display = "none";
  });

  /* --- Listen for close/theme msgs from widget iframe --- */
  window.addEventListener("message", (e) => {
    if (e.data === "close-widget") {
      isOpen = false;
      bubble.classList.remove("open");
      container.classList.remove("open");
    } else if (e.data === "toggle-theme") {
      container.classList.toggle("light-mode");
    }
  });
})();
