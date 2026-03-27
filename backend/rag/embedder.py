"""
backend/rag/embedder.py
-----------------------
Wraps sentence-transformers for offline text embedding.
Used both at KB build time and query time.
"""

import logging
from typing import List

log = logging.getLogger("bankbot.rag")


class Embedder:
    """Offline sentence embedder using all-MiniLM-L6-v2."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def load(self):
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer
        log.info("Loading embedder: %s", self.model_name)
        self._model = SentenceTransformer(self.model_name, local_files_only=True)
        log.info("✅ Embedder ready")

    def encode(self, texts: List[str]) -> List[List[float]]:
        if self._model is None:
            raise RuntimeError("Embedder not loaded. Call .load() first.")
        return self._model.encode(texts, show_progress_bar=False).tolist()
