"""Chunker sémantique — découpage de texte avec overlap (D8).

Pure function, sans état ni effet de bord.
Stratégie KISS : paragraphes → phrases → overlap à cheval.
"""

import re

_CHUNK_SEPARATOR = "\n\n"


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    doc_id: str = "",
) -> list[dict]:
    """Découpe un texte en chunks sémantiques avec overlap.

    Retourne une liste de dicts :
    ``{"text": str, "metadata": {"doc_id": str, "chunk_index": int, "total_chunks": int}}``
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = _split_paragraphs(text)
    chunks = []
    buffer = ""

    for para in paragraphs:
        segments = _split_segments(para, chunk_size)
        for seg in segments:
            if len(buffer) + len(seg) <= chunk_size or not buffer:
                buffer += seg
            else:
                chunks.append(buffer)
                overlap_text = _take_overlap(buffer, overlap)
                buffer = overlap_text + seg

    if buffer.strip():
        chunks.append(buffer)

    result = []
    for i, chunk in enumerate(chunks):
        m = {"doc_id": doc_id, "chunk_index": i, "total_chunks": len(chunks)}
        result.append({"text": chunk.strip(), "metadata": m})

    return result


def _split_paragraphs(text: str) -> list[str]:
    """Sépare le texte en paragraphes."""
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip()]


def _split_segments(text: str, chunk_size: int) -> list[str]:
    """Découpe un paragraphe en segments <= chunk_size (par phrases)."""
    if len(text) <= chunk_size:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    segments = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= chunk_size:
            current += sent + " "
        else:
            if current.strip():
                segments.append(current.strip() + " ")
            if len(sent) > chunk_size:
                sub = _hard_split(sent, chunk_size)
                segments.extend(sub)
                current = ""
            else:
                current = sent + " "
    if current.strip():
        segments.append(current.strip())
    return segments


def _hard_split(text: str, chunk_size: int) -> list[str]:
    """Découpage forcé d'une très longue phrase (fallback)."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def _take_overlap(text: str, overlap: int) -> str:
    """Prend les *overlap* derniers caractères d'un texte."""
    if not text or overlap <= 0:
        return ""
    return text[-overlap:]


__all__ = ["chunk_text"]
