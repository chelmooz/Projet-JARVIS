"""PipelineService — Exécute des pipelines multi-étapes configurables en YAML."""

from __future__ import annotations

import inspect
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import yaml

from config.constants import DEFAULT_MODEL, PROJECT_DIR
from models import Pipeline, PipeStep
from ports.pipeline import PipelinePort
from services.adapters.protocols import ITraceStore, TraceRecord

_logger = logging.getLogger("jarvis.pipeline")

PIPELINES_DIR = os.path.join(PROJECT_DIR, "config", "pipelines")
RETRY_DELAY = 0.5
MAX_ERROR_LENGTH = 200


class PipelineError(Exception):
    """Exception levée quand un pipeline est introuvable ou mal configuré."""


class PipelineService(PipelinePort):
    """Moteur d'exécution de pipelines multi-étapes.

    Chaque pipeline est défini dans un fichier YAML sous ``config/pipelines/``.
    Supporte les politiques d'erreur par étape : abort (défaut), skip, retry.
    """

    def __init__(
        self,
        agent_runner: Any | None = None,
        inference: Any | None = None,
        memory: Any | None = None,
        model_selector: Any | None = None,
        trace_store: ITraceStore | None = None,
        max_retries: int = 3,
    ) -> None:
        self._agent_runner = agent_runner
        self._inference = inference
        self._memory = memory
        self._model_selector = model_selector
        self._trace_store = trace_store
        self._max_retries = max_retries
        self._pipelines: dict[str, Pipeline] = {}

        self._supports_model = self._check_runner_signature()

        self._load_pipelines()

    # ─── Initialisation ───────────────────────────────────────────────

    def _check_runner_signature(self) -> bool:
        """Vérifie si l'agent_runner accepte un 3e argument 'model'."""
        if self._agent_runner is None:
            return False
        try:
            sig = inspect.signature(self._agent_runner)
            return len(sig.parameters) >= 3
        except (ValueError, TypeError):
            return False

    def _load_pipelines(self) -> None:
        """Charge les pipelines depuis le répertoire de configuration."""
        if not os.path.isdir(PIPELINES_DIR):
            return

        seen_ids: set[str] = set()
        for fname in sorted(os.listdir(PIPELINES_DIR)):
            if not fname.endswith((".yaml", ".yml")):
                continue
            self._load_single_pipeline(fname, seen_ids)

    def _load_single_pipeline(self, fname: str, seen_ids: set[str]) -> None:
        """Charge et enregistre un fichier pipeline YAML unique."""
        path = os.path.join(PIPELINES_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "pipeline" not in data:
                return

            pipeline_data = data["pipeline"]
            pid = pipeline_data["id"]

            if pid in seen_ids:
                _logger.warning(
                    "ID de pipeline dupliqué '%s' dans %s — écrase le précédent",
                    pid, fname,
                )

            seen_ids.add(pid)
            steps = [PipeStep(**s) for s in pipeline_data.get("steps", [])]
            self._pipelines[pid] = Pipeline(
                id=pid,
                steps=steps,
                on_error=pipeline_data.get("on_error", "abort"),
            )
        except Exception as e:
            _logger.exception("Erreur chargement pipeline %s: %s", fname, e)

    # ─── API publique ─────────────────────────────────────────────────

    def register(self, pipeline: Pipeline) -> None:
        """Enregistre un pipeline en mémoire (surcharge si ID existant)."""
        self._pipelines[pipeline.id] = pipeline

    def list(self) -> list[dict[str, Any]]:
        """Retourne la liste des pipelines disponibles."""
        return [
            {"id": pid, "steps": len(p.steps), "on_error": p.on_error}
            for pid, p in self._pipelines.items()
        ]

    def get(self, pipeline_id: str) -> Pipeline | None:
        """Retourne un pipeline par son ID, ou None s'il n'existe pas."""
        return self._pipelines.get(pipeline_id)

    def run(
        self, pipeline_id: str, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Exécute un pipeline complet et capitalise la trace."""
        pipeline = self._resolve_pipeline(pipeline_id)
        ctx = {**(context or {})}
        results = self._execute_all_steps(pipeline, task, ctx)

        if self._has_fatal_error(results):
            return self._build_failure(pipeline_id, results)

        self._capitalize_trace(pipeline_id, task)

        return {
            "pipeline": pipeline_id,
            "steps": len(results),
            "results": results,
            "error": None,
        }

    # ─── Résolution ───────────────────────────────────────────────────

    def _resolve_pipeline(self, pipeline_id: str) -> Pipeline:
        """Retourne le pipeline ou lève PipelineError."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise PipelineError(f"Pipeline '{pipeline_id}' introuvable")
        return pipeline

    # ─── Exécution des étapes ─────────────────────────────────────────

    def _execute_all_steps(
        self, pipeline: Pipeline, task: str, ctx: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Parcourt les étapes séquentiellement, retourne la liste des résultats."""
        results: list[dict[str, Any]] = []

        for step in pipeline.steps:
            result, error = self._execute_with_retry(step, task, ctx)

            if error:
                self._record_step_error(step, error, results)
                if step.on_error != "skip":
                    break
            else:
                self._record_step_success(step, result, results, ctx, task, pipeline.id)

        return results

    def _execute_step(self, step: PipeStep, task: str, context: dict[str, Any]) -> str:
        """Exécute une étape unique via agent_runner ou inference."""
        prompt = step.prompt_template.format(task=task, **context)

        if self._agent_runner and step.agent_key:
            return self._run_via_agent(step, prompt, task)

        if self._inference:
            return self._run_via_inference(step, prompt, task)

        raise PipelineError("Aucun agent_runner ni inference configuré")

    def _run_via_agent(self, step: PipeStep, prompt: str, task: str) -> str:
        """Délègue l'exécution à l'agent_runner."""
        model = (
            self._model_selector(step.agent_key, task)
            if self._model_selector else None
        )
        if self._supports_model:
            return self._agent_runner(step.agent_key, prompt, model)
        return self._agent_runner(step.agent_key, prompt)

    def _run_via_inference(self, step: PipeStep, prompt: str, task: str) -> str:
        """Délègue l'exécution au service d'inférence."""
        model = (
            self._model_selector(step.agent_key, task)
            if self._model_selector else DEFAULT_MODEL
        )
        raw = self._inference.query(prompt, model)
        return self._extract_response(raw)

    def _extract_response(self, raw: Any) -> str:
        """Extrait la chaîne de réponse d'un résultat d'inférence."""
        if hasattr(raw, "data") and isinstance(raw.data, dict):
            return raw.data.get("response", str(raw))
        if isinstance(raw, dict):
            return raw.get("response", str(raw))
        return str(raw)

    # ─── Retry ────────────────────────────────────────────────────────

    def _execute_with_retry(
        self, step: PipeStep, task: str, ctx: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Exécute une étape avec retry jusqu'à _max_retries tentatives."""
        for attempt in range(self._max_retries + 1):
            try:
                result = self._execute_step(step, task, ctx)
                return result, None
            except Exception as e:
                _logger.exception("Erreur étape '%s'", step.name)

                if step.on_error == "retry" and attempt < self._max_retries:
                    self._wait_before_retry(attempt, step.name)
                else:
                    return None, str(e)[:MAX_ERROR_LENGTH]

        return None, "Limite de retry atteinte"

    def _wait_before_retry(self, attempt: int, step_name: str) -> None:
        """Attend avant une nouvelle tentative de retry."""
        delay = RETRY_DELAY * (attempt + 1)
        _logger.warning("Retry %d/%d pour '%s'", attempt + 1, self._max_retries, step_name)
        time.sleep(delay)

    # ─── Enregistrement des résultats d'étape ─────────────────────────

    def _record_step_success(
        self,
        step: PipeStep,
        result: str,
        results: list[dict[str, Any]],
        ctx: dict[str, Any],
        task: str,
        pipeline_id: str,
    ) -> None:
        """Enregistre un succès d'étape et met à jour le contexte."""
        results.append({
            "step": step.name,
            "agent": step.agent_key,
            "response": result,
            "error": None,
        })
        ctx[step.name] = result

        if self._memory:
            self._memory.update_habits({
                "task": task,
                "pipeline": pipeline_id,
                "step": step.name,
            })

    def _record_step_error(
        self, step: PipeStep, error_msg: str, results: list[dict[str, Any]]
    ) -> None:
        """Enregistre une erreur d'étape dans la liste des résultats."""
        results.append({
            "step": step.name,
            "agent": step.agent_key,
            "response": None,
            "error": error_msg,
        })

    # ─── Construction de la réponse ───────────────────────────────────

    def _has_fatal_error(self, results: list[dict[str, Any]]) -> bool:
        """Vérifie si la dernière étape a échoué de manière fatale."""
        if not results:
            return False
        last = results[-1]
        return last.get("error") is not None

    def _build_failure(
        self, pipeline_id: str, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Construit le dict de réponse en cas d'échec."""
        last_error = results[-1].get("error", "Erreur inconnue")
        return {
            "pipeline": pipeline_id,
            "steps": len(results),
            "results": results,
            "error": last_error,
        }

    # ─── Capitalisation (MT 7.1) ──────────────────────────────────────

    def _capitalize_trace(self, pipeline_id: str, task: str) -> None:
        """Écrit la trace dans le sidecar si un store est configuré."""
        if not self._trace_store:
            return
        try:
            record = self._build_trace_record(pipeline_id, task)
            self._trace_store.append(record)
        except Exception:
            _logger.exception(
                "Échec capitalisation trace pipeline='%s'", pipeline_id
            )

    def _build_trace_record(self, pipeline_id: str, task: str) -> TraceRecord:
        """Construit un TraceRecord pour la capitalisation post-pipeline."""
        return TraceRecord(
            trace_id=str(uuid.uuid4()),
            pipeline_id=pipeline_id,
            query=task,
            retrieved_chunk_ids=[],
            judge_score=0.0,
            judge_reason="",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# Alias backward-compat
PipelineEngine = PipelineService


__all__ = ["PipelineError", "PipelineService", "PipelineEngine"]