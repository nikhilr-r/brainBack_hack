"""
backend/llm/ollama_client.py
-----------------------------
Calls the local Ollama server for LLM generation.
Zero internet. Fully offline.

Responsibilities:
  - Detect which Ollama model is available on startup
  - Build the grounded prompt (system + history + context)
  - Call Ollama /api/chat endpoint over localhost
  - Return clean response text
"""

import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Optional

log = logging.getLogger("bankbot.llm")


class OllamaClient:
    """HTTP client for local Ollama LLM server."""

    def __init__(self, cfg):
        self.cfg         = cfg
        self.active_model: Optional[str] = None

    def detect_model(self) -> Optional[str]:
        """
        Query Ollama for pulled models and pick the best available one.
        Prioritises cfg.OLLAMA_MODEL (set via --llm flag) before trying fallback list.
        """
        try:
            req  = urllib.request.urlopen(f"{self.cfg.OLLAMA_HOST}/api/tags", timeout=3)
            data = json.loads(req.read())
            pulled = [m["name"] for m in data.get("models", [])]
            pulled_bases = [m.split(":")[0] for m in pulled]
            log.info("Ollama pulled models: %s", pulled)

            # 1. Try the user's explicitly requested model FIRST (Exact Match)
            primary = self.cfg.OLLAMA_MODEL
            if primary in pulled:
                self.active_model = primary
                log.info("✅ Ollama model selected (exact match): %s", self.active_model)
                return self.active_model

            # 2. Try the user's base name (e.g. 'phi3' matches 'phi3:mini')
            primary_base = primary.split(":")[0]
            if primary_base in pulled_bases:
                for p in pulled:
                    if p.startswith(primary_base + ":") or p == primary_base:
                        self.active_model = p
                        log.info("✅ Ollama model selected (base match): %s", self.active_model)
                        return self.active_model

            # 3. Fall back through the configured list
            for candidate in self.cfg.OLLAMA_FALLBACK:
                base = candidate.split(":")[0]
                if base in pulled_bases or candidate in pulled:
                    for p in pulled:
                        if p.startswith(base + ":") or p == base:
                            self.active_model = p
                            log.info("✅ Ollama model selected (fallback): %s", self.active_model)
                            return self.active_model

            log.warning("⚠️  No suitable Ollama model found. Run: ollama pull %s", primary)
            return None

        except Exception as e:
            log.warning("⚠️  Ollama not reachable at %s — %s", self.cfg.OLLAMA_HOST, e)
            return None

    def generate(
        self,
        system_prompt: str,
        user_text: str,
        history: List[Dict[str, str]],
    ) -> str:
        """
        Generate a response from the local LLM.

        Args:
            system_prompt: Filled-in system prompt (with context injected)
            user_text:     Current user utterance
            history:       List of {"user": ..., "bot": ...} dicts

        Returns:
            Response string. Falls back to a safe message if LLM is unavailable.
        """
        if not self.active_model:
            from config.prompts import LLM_UNAVAILABLE
            return LLM_UNAVAILABLE.get("en")

        # Build message array: system → history turns → current user
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history[-(self.cfg.SESSION_MAX_TURNS):]:
            messages.append({"role": "user",      "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["bot"]})
        messages.append({"role": "user", "content": user_text})

        payload = json.dumps({
            "model":   self.active_model,
            "messages": messages,
            "stream":  False,
            "options": {
                "num_ctx":        512,    # Tight budget: prompt + 1 RAG doc + answer
                "num_predict":    80,     # ~2 sentences - ample for banking answers
                "num_thread":     8,      # Use all CPU cores
                "temperature":    self.cfg.LLM_TEMPERATURE,
                "top_p":          self.cfg.LLM_TOP_P,
                "repeat_penalty": 1.1,
                "stop":           self.cfg.LLM_STOP,
            },
        }).encode()

        req = urllib.request.Request(
            f"{self.cfg.OLLAMA_HOST}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.cfg.LLM_TIMEOUT_S) as resp:
            data = json.loads(resp.read())

        return data["message"]["content"].strip()
