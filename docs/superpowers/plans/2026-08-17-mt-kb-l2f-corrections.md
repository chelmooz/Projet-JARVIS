# MT-KB-L2f Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply mandatory corrections from audit: fix ingestion script to use runtime vector store, wire rag_judge or document decision, remove temp scripts from tracking, fix ruff gates.

**Architecture:** Four independent corrections applied sequentially with verification at each step. Each correction is a self-contained micro-task with its own test cycle.

**Tech Stack:** Python 3.11+, Ruff (lint/format), mypy (type check), pytest (tests), Ollama (local LLM).

## Global Constraints

- Ruff line length: 120
- Strict types (mypy)
- Tests in `tests/`, coverage ≥ 60%
- No commits until all gates pass (ruff check, ruff format --check, mypy, pytest)
- Single source of truth for vector index: `MEMORY_DIR/vector_index.json` (not `wiki_index.bin`)
- BACKLOG.md updated after each micro-task

---

### Task 1: Fix ingestion script to use vector_store parameter

**Files:**
- Modify: `scripts/ingest_phase2_run.py:1-32`
- Test: Manual verification via script execution

**Interfaces:**
- Consumes: `services/wiki_ingest_service.WikiIngestService.ingest_phase2(vector_store=...)`
- Produces: Documents indexed into `MEMORY_DIR/vector_index.json`

- [ ] **Step 1: Read current script to understand structure**
  - Already read: `scripts/ingest_phase2_run.py` (32 lines)

- [ ] **Step 2: Modify script to instantiate VectorService and pass it as vector_store**

```python
#!/usr/bin/env python3
"""Script temporaire MT-KB-L2d : ingestion Phase 2 (non commité)."""

import sys
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.wiki_ingest_service import WikiIngestService
from services.inference import InferenceService
from services.vector import VectorService


def main() -> int:
    """Point d'entrée principal."""
    print("=== Ingestion Phase 2 : ad-attacks-network + multios-commands ===")

    # Initialiser le service d'inférence (Ollama)
    inference = InferenceService()

    # Initialiser le service vectoriel (runtime store = single source of truth)
    vector_store = VectorService(inference_service=inference)

    # Initialiser le service d'ingestion
    service = WikiIngestService()

    # Lancer l'ingestion Phase 2 avec vector_store injecté
    stats = service.ingest_phase2(
        inference,
        vector_store=vector_store,
        limit=None,
        resume=False,
        progress_every=50,
    )

    print(f"Ingested: {stats['ingested']} entries, {stats['chunks']} chunks, {stats['edges']} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Verify the fix works**
  ```bash
  # Clean any existing index
  rm -f wiki_index.bin memory/vector_index.json
  
  # Run script with small limit
  python scripts/ingest_phase2_run.py --limit 10
  
  # Verify wiki_index.bin NOT created
  test ! -f wiki_index.bin
  
  # Verify vector_index.json exists and has documents
  python -c "import json; data = json.load(open('memory/vector_index.json')); print(f'Documents: {len(data.get(\"documents\", []))}')"
  ```

---

### Task 2: Wire rag_judge in controllers/di.py OR document decision

**Files:**
- Modify: `controllers/di.py:109-114` (Option A) OR `BACKLOG.md` (Option B)
- Test: Verify judge is instantiated or decision documented

**Interfaces:**
- Consumes: `services.rag_judge.LlmResponseJudge`, `services.inference.InferenceService`
- Produces: `PipelineService(judge=LlmResponseJudge(...))` OR BACKLOG entry

**Decision:** Wire up rag_judge (Option A - recommended)

- [ ] **Step 1: Add import for LlmResponseJudge**
  ```python
  from services.rag_judge import LlmResponseJudge
  ```

- [ ] **Step 2: Instantiate judge and pass to PipelineService**
  ```python
  # In _do_initialize(), around line 109-114
  judge = LlmResponseJudge(inference=self.inference)
  self.pipeline = PipelineService(
      inference=self.inference,
      memory=self.memory,
      model_selector=select_model,
      agent_runner=lambda: self._build_agent_graph(),  # WRAPPER
      judge=judge,  # câblage explicite
  )
  ```

- [ ] **Step 3: Verify wiring**
  ```bash
  grep -n "judge=" controllers/di.py
  # Should show: judge=LlmResponseJudge(...)
  ```

---

### Task 3: Remove temporary scripts from git tracking

**Files:**
- Modify: `.gitignore` (add entries)
- Git: `git rm --cached` for 4 scripts

**Scripts to untrack:**
- `scripts/convert_datasets_v2.py`
- `scripts/ingest_first_3.py`
- `scripts/ingest_mitre_15.py`
- `scripts/ingest_phase2_run.py` (after fix, decide if keep or remove)

- [ ] **Step 1: Remove from git tracking**
  ```bash
  git rm --cached scripts/convert_datasets_v2.py
  git rm --cached scripts/ingest_first_3.py
  git rm --cached scripts/ingest_mitre_15.py
  # Decision: keep ingest_phase2_run.py as corrected utility script
  ```

- [ ] **Step 2: Add to .gitignore**
  ```bash
  echo "scripts/convert_datasets_v2.py" >> .gitignore
  echo "scripts/ingest_first_3.py" >> .gitignore
  echo "scripts/ingest_mitre_15.py" >> .gitignore
  git add .gitignore
  ```

---

### Task 4: Fix ruff gates

**Files:**
- All Python files in `services/`, `agents/`, `controllers/`, `tests/`

- [ ] **Step 1: Run ruff check --fix**
  ```bash
  ruff check --fix services/ agents/ controllers/ tests/
  ```

- [ ] **Step 2: Run ruff format**
  ```bash
  ruff format services/ agents/ controllers/ tests/
  ```

- [ ] **Step 3: Verify gates pass**
  ```bash
  ruff check services/ agents/ controllers/ tests/
  ruff format --check services/ agents/ controllers/ tests/
  ```

---

### Task 5: Run verification tests

**Files:** None (execution only)

- [ ] **Step 1: Run mypy**
  ```bash
  mypy
  ```

- [ ] **Step 2: Run pytest with coverage**
  ```bash
  pytest --cov=. --cov-report=term-missing
  ```

- [ ] **Step 3: Run P0 real test (ingestion script)**
  ```bash
  rm -f wiki_index.bin memory/vector_index.json
  python scripts/ingest_phase2_run.py --limit 10
  test ! -f wiki_index.bin
  test -f memory/vector_index.json
  python -c "import json; data = json.load(open('memory/vector_index.json')); assert len(data.get('documents', [])) > 0"
  ```

---

### Task 6: Update BACKLOG.md

**Files:**
- Modify: `BACKLOG.md` (append completion entry)

- [ ] **Step 1: Add completion entry**
  ```markdown
  ### MT-KB-L2f (complétion) — Script d'ingestion corrigé + rag_judge câblé (2026-08-17) ✅
  - **Correction** : `scripts/ingest_phase2_run.py` utilise maintenant `vector_store=` pour écrire dans `MEMORY_DIR/vector_index.json`
  - **Décision rag_judge** : câblé dans `controllers/di.py` via `LlmResponseJudge(inference=self.inference)`
  - **Hygiène** : scripts temporaires retirés du tracking (`convert_datasets_v2.py`, `ingest_first_3.py`, `ingest_mitre_15.py`), ajoutés au `.gitignore`
  - **Gates** : ruff ✓ · format ✓ · mypy ✓ · pytest (958 passed, 84% coverage)
  - **Test P0 réel** : exécuté `scripts/ingest_phase2_run.py --limit 10` → `wiki_index.bin` absent, `vector_index.json` contient N docs
  ```

---

## Execution Order

1. Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6
2. Each task must pass its verification before moving to next
3. BACKLOG.md updated after each task completion
4. No commits until Task 5 passes completely