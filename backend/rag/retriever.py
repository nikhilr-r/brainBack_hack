"""
backend/rag/retriever.py
------------------------
FAISS-based Retrieval-Augmented Generation (RAG).

- Fully offline
- No compilation issues
- Fast similarity search
"""

import logging
from dataclasses import dataclass
from typing import List
import numpy as np
import faiss

log = logging.getLogger("bankbot.rag")


@dataclass
class RAGResult:
    documents: List[str]
    similarity: float
    context: str        # All docs (for fallback / display)
    top_context: str    # Only the best doc (for LLM — prevents confusion)


class Retriever:
    """FAISS-backed retriever for bank knowledge base."""

    def __init__(self, cfg, embedder):
        self.cfg = cfg
        self.embedder = embedder
        self.index = None
        self.documents = []

    def build(self, documents: List[str]):
        """
        Build FAISS index from documents.
        """
        log.info("Building FAISS knowledge base (%d entries)...", len(documents))

        self.documents = documents
        embeddings = self.embedder.encode(documents)

        embeddings = np.array(embeddings).astype("float32")

        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings)

        log.info("✅ FAISS index ready — %d chunks indexed", len(documents))

    def retrieve(self, query: str) -> RAGResult:
        """
        Retrieve top-K relevant documents using FAISS.
        """
        if self.index is None:
            raise RuntimeError("Retriever not built. Call .build() first.")

        query_emb = self.embedder.encode([query])
        query_emb = np.array(query_emb).astype("float32")

        D, I = self.index.search(query_emb, self.cfg.RAG_TOP_K)

        docs = [self.documents[i] for i in I[0]]

        # Convert L2 distance to similarity (approx)
        best_sim = max(0.0, 1.0 - (D[0][0] / 2.0)) if len(D[0]) > 0 else 0.0

        context = "\n".join(f"• {d}" for d in docs)

        log.info("RAG → sim=%.2f  top_doc='%s…'", best_sim, docs[0][:50] if docs else "")

        return RAGResult(
            documents=docs,
            similarity=best_sim,
            context=context,
            top_context=f"• {docs[0]}" if docs else "",  # Only #1 doc for LLM
        )