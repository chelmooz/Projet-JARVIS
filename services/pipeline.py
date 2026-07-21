"""PipelineService — Exécute des pipelines multi-étapes configurables en YAML."""

from __future__ import annotations

import inspect
import logging
import os
import time
from typing import Any

import yaml

from config.constants import DEFAULT_MODEL, PROJECT_DIR
from models import Pipeline, PipeStep
from ports.pipeline import PipelinePort

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
        max_retries: int = 3,
    ) -> None:
        self._agent_runner = agent_runner
        self._inference = inference
        self._memory = memory
        self._model_selector = model_selector
        self._max_retries = max_retries
        self._pipelines: dict[str, Pipeline] = {}
        
        # Cache le résultat de l'inspection de signature pour éviter de le recalculer
        # à chaque exécution d'étape.
        self._supports_model = self._check_runner_signature()
        
        self._load_pipelines()

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
            
            path = os.path.join(PIPELINES_DIR, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                
                if not data or "pipeline" not in data:
                    continue
                
                p = data["pipeline"]
                pid = p["id"]
                
                if pid in seen_ids:
                    _logger.warning("ID de pipeline dupliqué '%s' dans %s — écrase le précédent", pid, fname)
                
                seen_ids.add(pid)
                steps = [PipeStep(**s) for s in p.get("steps", [])]
                self._pipelines[pid] = Pipeline(
                    id=pid,
                    steps=steps,
                    on_error=p.get("on_error", "abort"),
                )
            except Exception as e:
                _logger.exception("Erreur chargement pipeline %s: %s", fname, e)

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

    def _execute_step(self, step: PipeStep, task: str, context: dict[str, Any]) -> str:
        """Exécute une étape unique via agent_runner ou inference."""
        prompt = step.prompt_template.format(task=task, **context)
        
        if self._agent_runner and step.agent_key:
            model = (
                self._model_selector(step.agent_key, task)
                if self._model_selector else None
            )
            if self._supports_model:
                return self._agent_runner(step.agent_key, prompt, model)
            return self._agent_runner(step.agent_key, prompt)
        
        if self._inference:
            model = (
                self._model_selector(step.agent_key, task)
                if self._model_selector else DEFAULT_MODEL
            )
            raw = self._inference.query(prompt, model)
            
            if hasattr(raw, "data") and isinstance(raw.data, dict):
                return raw.data.get("response", str(raw))
            if isinstance(raw, dict):
                return raw.get("response", str(raw))
            return str(raw)
        
        raise PipelineError("Aucun agent_runner ni inference configuré")

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
                    delay = RETRY_DELAY * (attempt + 1)
                    _logger.warning("Retry %d/%d pour '%s'", attempt + 1, self._max_retries, step.name)
                    # time.sleep conservé : fonction sync appelée depuis une route synchrone.
                    time.sleep(delay)
                else:
                    return None, str(e)[:MAX_ERROR_LENGTH]
        
        return None, "Limite de retry atteinte"

    def _handle_step_error(
        self,
        step: PipeStep,
        error_msg: str,
        results: list[dict[str, Any]],
        pipeline_id: str,
    ) -> dict[str, Any] | None:
        """Traite une erreur selon step.on_error. Retourne un dict d'échec si abort, None si skip."""
        results.append({
            "step": step.name,
            "agent": step.agent_key,
            "response": None,
            "error": error_msg,
        })
        
        if step.on_error == "skip":
            return None
        
        if step.on_error == "retry":
            results[-1]["error"] = f"{error_msg} (échec après {self._max_retries} tentatives)"
        
        return {
            "pipeline": pipeline_id,
            "steps": len(results),
            "results": results,
            "error": error_msg,
        }

    def run(
        self, pipeline_id: str, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Exécute un pipeline complet."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise PipelineError(f"Pipeline '{pipeline_id}' introuvable")

        ctx = {**(context or {})}
        results: list[dict[str, Any]] = []

        for step in pipeline.steps:
            result, error = self._execute_with_retry(step, task, ctx)
            
            if error:
                failure = self._handle_step_error(step, error, results, pipeline_id)
                if failure:
                    return failure
            else:
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

        return {
            "pipeline": pipeline_id,
            "steps": len(results),
            "results": results,
            "error": None,
        }


# Alias backward-compat
PipelineEngine = PipelineService


__all__ = ["PipelineError", "PipelineService", "PipelineEngine"]
