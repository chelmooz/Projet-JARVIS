"""services/ocr.py — OCR déterministe via RapidOCR (ONNX, 100% offline).

Remplace l'agent vision LLM (moondream) pour l'extraction de texte : RapidOCR
lit les pixels directement (détection + reconnaissance de caractères), sans
génération de langage — fiable pour du texte dense (documents, captures
d'écran), là où un petit modèle vision hallucine.

Aucun binaire externe requis (contrairement à Tesseract) : pip pur
(rapidocr + onnxruntime), cohérent avec la contrainte 100% portable USB.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

_logger = logging.getLogger(__name__)

_engine: Any = None


def _get_engine() -> Any:
    """Charge le moteur RapidOCR paresseusement (import/init coûteux, à ne
    payer qu'à la première requête OCR, pas au démarrage de l'app)."""
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR

        _engine = RapidOCR()
    return _engine


def run_ocr(image_b64: str) -> dict[str, Any]:
    """Exécute l'OCR sur une image encodée en base64 (sans préfixe data URI).

    Retourne {"text": str, "lines": int, "error": str | None}.
    """
    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        return {"text": "", "lines": 0, "error": f"Image invalide (base64) : {e}"}

    try:
        engine = _get_engine()
        result = engine(image_bytes)
    except Exception as e:
        _logger.error("RapidOCR failed", exc_info=True)
        return {"text": "", "lines": 0, "error": f"Erreur OCR : {e}"}

    txts = tuple(result.txts) if result and result.txts else ()
    text = "\n".join(t for t in txts if t)
    return {"text": text, "lines": len(txts), "error": None}
