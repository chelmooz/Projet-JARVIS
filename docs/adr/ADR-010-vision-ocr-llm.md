# ADR-010 — Vision : OCR (RapidOCR) + analyse LLM (Qwen2.5), sans modèle multimodal

- **Statut** : Accepté
- **Date** : 13/08/2026

## Contexte

Le traitement des images dans JARVIS reposait à l'origine sur un modèle vision
multimodal Ollama (`moondream`, ~1,4 Go). Celui-ci a été retiré (non réassigné
après remplacement), ce qui a conduit à un fallback sur **RapidOCR**
(`services/ocr.py`) pour l'extraction de texte — déterministe, 100% offline,
sans modèle Ollama.

Or RapidOCR ne fait qu'**extraire du texte brut** : il ne « comprend » pas le
contenu. Le pipeline actuel (`agents/vision.py`, `POST /api/vision`) renvoyait
donc le texte OCR tel quel à l'utilisateur, sans analyse. Pour une image
contenant une liste de questions, le système se contentait de recracher les
lignes détectées — pas une réponse à la consigne.

Contrainte : environnement 100% local, portable (clé USB), pas de cloud. Le
modèle d'analyse doit être déjà disponible et résident en VRAM pour éviter un
double chargement.

## Décision

Le traitement d'une image se fait en **deux étapes découplées** :

1. **Extraction** : `RapidOCR` (`services/ocr.py`) lit les pixels et renvoie le
   texte brut. Aucun modèle Ollama n'est sollicité à cette étape.
2. **Analyse** : le texte OCR est injecté comme contexte dans un **LLM texte**
   (`Qwen2.5-7B-Instruct-GGUF:Q4_K_M`, voir `VISION_ANALYSIS_MODEL` dans
   `agents/vision.py`) avec la consigne de l'utilisateur. C'est ce LLM qui
   produit la réponse finale.

Modèle d'analyse retenu : **`Qwen2.5-7B`** (généraliste, multilingue FR, déjà
résident en VRAM via `keep_alive` du profil techlead). Il est imposé en dur
(Option A) et résolu via `services/selector.py::select_vision_analysis_model()`.

Deux points d'entrée exposent le pipeline :

- **Chat** (`@vision` ou image droppée) → `agents/vision.py` (`VisionAgent.run`)
  appelé par l'orchestrateur (`services/orchestrator.py`).
- **Endpoint dédié** `POST /api/vision` → `controllers/routes/agents.py`
  (`handle_vision`).

En l'absence d'image, `@vision` retombe sur le profil **designer** (texte seul).
Si l'analyse LLM échoue, les deux chemins **dégradent gracieusement** vers le
texte OCR brut (pas de fail-fast sur l'analyse).

## Conséquences

- Avantage : analyse compréhensible du contenu image (comportement équivalent
  à l'ancien `moondream`), sans dépendre d'un modèle multimodal lourd/absent.
- Avantage : découplage OCR (CPU, déterministe) / LLM (VRAM) — chaque étape
  peut évoluer indépendamment.
- Coût : latence = OCR (~200-500 ms) + LLM (~1-3 s). Acceptable pour de
  l'analyse visuelle ponctuelle.
- Télémétrie : `select_vision_model()` renvoie toujours la sentinelle
  `"rapidocr"` (suivi de l'étape OCR) ; le modèle d'analyse réel est tracé
  séparément dans `analytics`.
- À documenter côté utilisateur : le README (section 🖼️ Vision) et `AGENTS.md`
  reflètent désormais « OCR + analyse Qwen2.5 », en remplacement des anciennes
  références `moondream` / `llava` / `llama3.2-vision`.
