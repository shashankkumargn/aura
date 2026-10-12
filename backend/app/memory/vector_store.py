"""Vector store and semantic retrieval for AURA policies and products."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POLICIES_FILE = DATA_DIR / "policies.json"
PRODUCTS_FILE = DATA_DIR / "seed_products.json"
INDEX_DIR = DATA_DIR / "faiss_index"
INDEX_META_FILE = INDEX_DIR / "index_docs.json"

_DOCS: list[str] = []
_IDF: dict[str, float] = {}
_DOC_VECTORS: list[dict[str, float]] = []


def _tokenize(text: str) -> list[str]:
    """Simple lowercase alphanumeric tokenization."""
    return re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())


def build_index() -> None:
    """Build knowledge index over policies.json and product descriptions."""
    global _DOCS, _IDF, _DOC_VECTORS
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    docs: list[str] = []

    # 1. Load policy documents
    if POLICIES_FILE.exists():
        with POLICIES_FILE.open("r", encoding="utf-8") as f:
            policies = json.load(f)
            for p in policies:
                docs.append(f"Policy: {p['title']} [{p['category']}] - {p['text']}")

    # 2. Load product descriptions
    if PRODUCTS_FILE.exists():
        with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
            products = json.load(f)
            for prod in products:
                docs.append(
                    f"Product: {prod['name']} ({prod.get('category')}, ₹{prod.get('price')}). "
                    f"Description: {prod.get('description', '')}"
                )

    _DOCS = docs

    # Compute term frequencies & document frequencies for TF-IDF
    num_docs = len(docs)
    df: dict[str, int] = {}
    doc_tfs: list[dict[str, int]] = []

    for doc in docs:
        tokens = _tokenize(doc)
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1
        doc_tfs.append(tf)

    _IDF = {
        term: math.log((num_docs + 1) / (count + 1)) + 1
        for term, count in df.items()
    }

    _DOC_VECTORS = []
    for tf in doc_tfs:
        vec: dict[str, float] = {}
        norm_sq = 0.0
        for term, count in tf.items():
            val = count * _IDF.get(term, 1.0)
            vec[term] = val
            norm_sq += val * val
        norm = math.sqrt(norm_sq) or 1.0
        for term in vec:
            vec[term] /= norm
        _DOC_VECTORS.append(vec)

    # Persist documents to index directory
    with INDEX_META_FILE.open("w", encoding="utf-8") as f:
        json.dump({"docs": _DOCS, "count": len(_DOCS)}, f, indent=2)


def _ensure_index() -> None:
    """Ensure index is loaded in memory."""
    if not _DOCS:
        if INDEX_META_FILE.exists():
            with INDEX_META_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                docs = data.get("docs", [])
                if docs:
                    build_index()
                    return
        build_index()


def search(query: str, k: int = 4) -> list[str]:
    """Perform semantic / relevance search over policy documents and product catalog; returns list[str]."""
    _ensure_index()
    tokens = _tokenize(query)
    if not tokens or not _DOCS:
        return _DOCS[:k]

    # Compute query vector
    q_tf: dict[str, int] = {}
    for t in tokens:
        q_tf[t] = q_tf.get(t, 0) + 1

    q_vec: dict[str, float] = {}
    norm_sq = 0.0
    for term, count in q_tf.items():
        val = count * _IDF.get(term, 1.0)
        q_vec[term] = val
        norm_sq += val * val
    norm = math.sqrt(norm_sq) or 1.0
    for term in q_vec:
        q_vec[term] /= norm

    # Score documents by cosine similarity
    scores: list[tuple[float, int]] = []
    for idx, doc_vec in enumerate(_DOC_VECTORS):
        score = sum(q_vec[term] * doc_vec.get(term, 0.0) for term in q_vec)
        scores.append((score, idx))

    scores.sort(key=lambda x: x[0], reverse=True)
    results = [_DOCS[idx] for score, idx in scores[:k] if score > 0.0]
    return results if results else _DOCS[:k]
