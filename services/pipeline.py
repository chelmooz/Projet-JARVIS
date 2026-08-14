"""PipelineService — Exécute des pipelines multi-étapes configurables en YAML."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import yaml

from config.constants import MAX_ADAPTIVE_ATTEMPTS, PROJECT_DIR
from models import Pipeline, PipeStep
from ports.pipeline import PipelinePort
from services.adapters.protocols import IResponseJudge, ITraceStore, IVectorSearch, TraceRecord
from services.pipeline_helpers import build_failure, build_hyde_query, has_fatal_error, is_stagnant
from services.pipeline_steps import (
    NonCallableRunnerError,
    _runner_supports_model,
    _should_retry,
    _wait_before_retry,
)
from services.rag_judge import JUDGE_THRESHOLD

_logger = logging.getLogger("jarvis.pipeline")

PIPELINES_DIR = os.path.join(PROJECT_DIR, "config", "pipelines")
DEFAULT_TOP_K = 3


class PipelineError(Exception):
    """Exception levée quand un pipeline est introuvable ou mal configuré."""


class PipelineService(PipelinePort):
    """Moteur d'exécution de pipelines multi-étapes YAML (politiques abort/skip/retry)."""

    def __init__(
        self,
        agent_runner: Any | None = None,
        inference: Any | None = None,
        memory: Any | None = None,
        model_selector: Any | None = None,
        trace_store: ITraceStore | None = None,
        vector_search: IVectorSearch | None = None,
        judge: IResponseJudge | None = None,
        max_retries: int = 3,
    ) -> None:
        self._agent_runner = agent_runner
        self._inference = inference
        self._memory = memory
        self._model_selector = model_selector
        self._trace_store = trace_store
        self._vector_search = vector_search
        self._judge = judge
        self._max_retries = max_retries
        self._pipelines: dict[str, Pipeline] = {}

        self._load_pipelines()

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
                _logger.warning("ID de pipeline dupliqué '%s' dans %s — écrase le précédent", pid, fname)

            seen_ids.add(pid)
            steps = [PipeStep(**s) for s in pipeline_data.get("steps", [])]
            self._pipelines[pid] = Pipeline(id=pid, steps=tuple(steps), on_error=pipeline_data.get("on_error", "abort"))
        except Exception as e:
            _logger.exception("Erreur chargement pipeline %s: %s", fname, e)

    # ─── API publique ─────────────────────────────────────────────────

    def register(self, pipeline: Pipeline) -> None:
        """Enregistre un pipeline en mémoire (surcharge si ID existant)."""
        self._pipelines[pipeline.id] = pipeline

    def list_pipelines(self) -> list[dict[str, Any]]:
        """Retourne la liste des pipelines disponibles."""
        return [{"id": pid, "steps": len(p.steps), "on_error": p.on_error} for pid, p in self._pipelines.items()]

    def get(self, pipeline_id: str) -> Pipeline | None:
        """Retourne un pipeline par son ID, ou None s'il n'existe pas."""
        return self._pipelines.get(pipeline_id)

    def run(self, pipeline_id: str, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Exécute un pipeline complet avec récupération pré-pipeline et capitalisation."""
        pipeline = self._resolve_pipeline(pipeline_id)
        ctx = {**(context or {})}

        return self._run_adaptive(pipeline, task, ctx) if self._judge else self._run_legacy(pipeline, task, ctx)

    def _build_success(self, pipeline_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Construit le dict de réponse en cas de succès."""
        return {"pipeline": pipeline_id, "steps": len(results), "results": results, "error": None}

    def _run_legacy(self, pipeline: Pipeline, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        """Exécution simple sans juge (backward compat)."""
        if similar_cases := self._retrieve_similar_cases(task):
            ctx["similar_cases"] = similar_cases

        results = self._execute_all_steps(pipeline, task, ctx)

        if has_fatal_error(results):
            return build_failure(pipeline.id, results)

        final_response = results[-1]["response"] if results else ""
        self._capitalize_trace(pipeline.id, task, similar_cases, final_response)

        return self._build_success(pipeline.id, results)

    def _run_adaptive(self, pipeline: Pipeline, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
        """Boucle adaptative HyDE + retry + arrêt mécanique sur score du juge."""
        judge = self._judge
        assert judge is not None  # Appelé uniquement depuis run() avec un juge
        query = task
        last_reason = ""

        for attempt in range(MAX_ADAPTIVE_ATTEMPTS):
            similar_cases, results = self._run_attempt(pipeline, query, ctx, attempt)

            if has_fatal_error(results):
                return build_failure(pipeline.id, results)

            final_response = results[-1]["response"] if results else ""
            chunk_texts = [c["text"] for c in similar_cases] if similar_cases else []
            judge_result = judge.evaluate(query, chunk_texts, final_response)
            score = judge_result.get("score", 0.0)
            reason = judge_result.get("reason", "")

            if score >= JUDGE_THRESHOLD or is_stagnant(reason, last_reason, attempt):
                self._capitalize_trace(pipeline.id, query, similar_cases, final_response, score, reason)
                return self._build_success(pipeline.id, results)

            last_reason = reason
            query = build_hyde_query(task, final_response)

        self._capitalize_trace(
            pipeline.id,
            query,
            similar_cases,
            final_response,
            judge_result.get("score", 0.0),
            judge_result.get("reason", ""),
        )
        return self._build_success(pipeline.id, results)

    def _run_attempt(
        self, pipeline: Pipeline, query: str, ctx: dict[str, Any], attempt: int
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Exécute une tentative unique : checkpoint + retrieval + étapes."""
        self._write_checkpoint(pipeline.id, query, attempt)
        similar_cases = self._retrieve_similar_cases(query)
        attempt_ctx = {**ctx, **({"similar_cases": similar_cases} if similar_cases else {})}
        return similar_cases, self._execute_all_steps(pipeline, query, attempt_ctx)

    def _write_checkpoint(self, pipeline_id: str, query: str, attempt: int) -> None:
        """Écrit un checkpoint sidecar avant chaque tentative (loop-engineering.md)."""
        if not self._trace_store:
            return
        record = TraceRecord(
            trace_id=str(uuid.uuid4()),
            pipeline_id=pipeline_id,
            query=query,
            retrieved_chunk_ids=[],
            judge_score=0.0,
            judge_reason="",
            status="checkpoint",
            timestamp=datetime.now(UTC).isoformat(),
        )
        self._trace_store.append(record)

    # ─── Résolution ───────────────────────────────────────────────────

    def _resolve_pipeline(self, pipeline_id: str) -> Pipeline:
        """Retourne le pipeline ou lève PipelineError."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise PipelineError(f"Pipeline '{pipeline_id}' introuvable")
        return pipeline

    # ─── Récupération pré-pipeline (MT 7.2) ───────────────────────────

    def _retrieve_similar_cases(self, task: str) -> list[dict[str, Any]]:
        """Recherche les cas similaires via le port IVectorSearch."""
        if not self._vector_search:
            return []
        try:
            return self._vector_search.search(task, top_k=DEFAULT_TOP_K)
        except Exception:
            _logger.exception("Échec récupération cas similaires task='%s'", task)
            return []

    # ─── Exécution des étapes ─────────────────────────────────────────

    def _execute_all_steps(self, pipeline: Pipeline, task: str, ctx: dict[str, Any]) -> list[dict[str, Any]]:
        """Parcourt les étapes séquentiellement, retourne les résultats."""
        state: dict[str, Any] = {"task": task, "context": ctx, "results": []}

        for step in pipeline.steps:
            if state.get("error") is not None and step.on_error != "skip":
                break

            state = self._execute_single_step(state, step, task)

            if state["results"] and state["results"][-1]["error"] is None:
                self._record_habits(task, pipeline.id, step)

        return cast("list[dict[str, Any]]", state["results"])

    def _execute_single_step(self, state: dict[str, Any], step: Any, task: str) -> dict[str, Any]:
        """Exécute une étape unique avec gestion des réessais (logique inline depuis pipeline_steps)."""
        if "context" not in state:
            state["context"] = {}
        if "results" not in state:
            state["results"] = []

        prompt = step.prompt_template.format(task=task, **state["context"])

        for attempt in range(self._max_retries + 1):
            try:
                result = None
                error = None

                if self._agent_runner is not None and step.agent_key:
                    if callable(self._agent_runner):
                        model = (
                            self._model_selector(step.agent_key, self._inference)
                            if self._model_selector is not None
                            else None
                        )
                        if _runner_supports_model(self._agent_runner):
                            result = self._agent_runner(step.agent_key, prompt, model)
                        else:
                            result = self._agent_runner(step.agent_key, prompt)
                    else:
                        raise NonCallableRunnerError(f"agent_runner non callable : {self._agent_runner!r}")
                elif self._inference is not None:
                    raw_result = self._inference.query(prompt, None)
                    if hasattr(raw_result, "data") and isinstance(raw_result.data, dict):
                        result = str(raw_result.data.get("response", str(raw_result)))
                    elif isinstance(raw_result, dict):
                        result = str(raw_result.get("response", str(raw_result)))
                    else:
                        result = str(raw_result)
                else:
                    error = "Aucun agent_runner ni inference configuré"

                if error is None:
                    state["results"].append(
                        {
                            "step": step.name,
                            "agent": step.agent_key,
                            "response": result,
                            "error": None,
                        }
                    )
                    state["context"][step.name] = result
                    break

                if _should_retry(step, attempt, self._max_retries):
                    _wait_before_retry(attempt, self._max_retries, step.name)
                    continue
                break

            except Exception as e:
                error = str(e)[:200]
                if _should_retry(step, attempt, self._max_retries):
                    _wait_before_retry(attempt, self._max_retries, step.name)
                    continue
                break

        else:
            error = error or "Erreur inconnue après tous les retries"

        if error is not None:
            state["error"] = error
            state["results"].append(
                {
                    "step": step.name,
                    "agent": step.agent_key,
                    "response": None,
                    "error": error,
                }
            )

        return state

    def _record_habits(self, task: str, pipeline_id: str, step: PipeStep) -> None:
        """Hook habits en frontière d'orchestration (dépend du contexte pipeline, pas de l'étape)."""
        if self._memory:
            entry = {"task": task, "pipeline": pipeline_id, "step": step.name}
            self._memory.update_habits(entry)

    # ─── Capitalisation (MT 7.1) ──────────────────────────────────────

    def _capitalize_trace(
        self,
        pipeline_id: str,
        task: str,
        chunks: list[dict[str, Any]],
        response: str,
        judge_score: float | None = None,
        judge_reason: str | None = None,
    ) -> None:
        """Écrit la trace dans le sidecar si un store est configuré."""
        if not self._trace_store:
            return
        try:
            record = self._build_trace_record(pipeline_id, task, chunks, response, judge_score, judge_reason)
            self._trace_store.append(record)
        except Exception:
            _logger.exception("Échec capitalisation trace pipeline='%s'", pipeline_id)

    def _build_trace_record(
        self,
        pipeline_id: str,
        task: str,
        chunks: list[dict[str, Any]],
        response: str,
        judge_score: float | None = None,
        judge_reason: str | None = None,
    ) -> TraceRecord:
        """Construit un TraceRecord pour la capitalisation post-pipeline."""
        chunk_ids = [c["id"] for c in chunks] if chunks else []
        chunk_texts = [c["text"] for c in chunks] if chunks else []

        if judge_score is None and self._judge:
            result = self._judge.evaluate(task, chunk_texts, response)
            judge_score = result.get("score", 0.0)
            judge_reason = result.get("reason", "")

        return TraceRecord(
            trace_id=str(uuid.uuid4()),
            pipeline_id=pipeline_id,
            query=task,
            retrieved_chunk_ids=chunk_ids,
            judge_score=judge_score or 0.0,
            judge_reason=judge_reason or "",
            timestamp=datetime.now(UTC).isoformat(),
        )


# Alias backward-compat
PipelineEngine = PipelineService

__all__ = ["PipelineError", "PipelineService", "PipelineEngine"]
