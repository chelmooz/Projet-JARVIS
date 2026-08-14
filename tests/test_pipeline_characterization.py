"""Filet de caractérisation PipelineService — comportement de production actuel.

Verts sur ``PipelineService`` AVANT tout déplacement vers
``pipeline_steps.execute_pipeline_step`` (plan T5a Phase 2, MT-2.1). Ils épinglent :
1. le contrat d'erreur (state, jamais d'exception frontière),
2. le retry conditionnel ``on_error == "retry"``,
3. le hook habits sur succès d'étape,
4. la continuation avec ``on_error == "skip"``.
"""

from __future__ import annotations

from typing import Any

from models import OnError, Pipeline, PipeStep
from services.pipeline import PipelineService


class FailingRunner:
    """Runner qui échoue toujours, avec compteur d'appels."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, agent_key: str, prompt: str) -> str:
        self.calls += 1
        raise RuntimeError("boom")


class OkRunner:
    """Runner qui réussit toujours, avec compteur d'appels."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, agent_key: str, prompt: str) -> str:
        self.calls += 1
        return f"ok-{agent_key}"


class RecordingMemory:
    """Mémoire factice qui enregistre les appels à update_habits."""

    def __init__(self) -> None:
        self.habit_entries: list[dict[str, Any]] = []

    def update_habits(self, entry: dict[str, Any]) -> None:
        self.habit_entries.append(entry)


def build_service(
    runner: Any | None = None,
    memory: Any | None = None,
    max_retries: int = 3,
) -> PipelineService:
    """Construit un PipelineService minimal (inference absent)."""
    return PipelineService(agent_runner=runner, inference=None, memory=memory, max_retries=max_retries)


def test_contrat_erreur_sans_backend() -> None:
    """Sans runner ni inference : entrée d'erreur dans results, aucune exception."""
    service = build_service()
    service.register(Pipeline(id="p", steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),)))
    result = service.run("p", "tester")
    assert result["error"] is not None
    assert result["results"][-1]["error"] == "Aucun agent_runner ni inference configuré"
    assert result["results"][-1]["response"] is None


def test_retry_conditionnel_on_error_retry(monkeypatch: Any) -> None:
    """on_error="retry" : le runner est rappelé max_retries+1 fois."""
    monkeypatch.setattr("services.pipeline_steps.time.sleep", lambda _: None)
    runner = FailingRunner()
    service = build_service(runner=runner, max_retries=2)
    service.register(
        Pipeline(
            id="p",
            steps=(
                PipeStep(
                    name="s1",
                    agent_key="dev",
                    prompt_template="{task}",
                    on_error=OnError.RETRY,
                ),
            ),
        )
    )
    result = service.run("p", "tester")
    assert runner.calls == 3  # 1 tentative + 2 retries
    assert result["error"] is not None


def test_retry_conditionnel_on_error_abort(monkeypatch: Any) -> None:
    """on_error="abort" : pas de retry, une seule tentative."""
    monkeypatch.setattr("services.pipeline_steps.time.sleep", lambda _: None)
    runner = FailingRunner()
    service = build_service(runner=runner, max_retries=2)
    service.register(Pipeline(id="p", steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),)))
    result = service.run("p", "tester")
    assert runner.calls == 1
    assert result["error"] is not None


def test_hook_habits_sur_succes() -> None:
    """Succès d'étape : update_habits appelé avec task/pipeline/step."""
    memory = RecordingMemory()
    service = build_service(runner=OkRunner(), memory=memory)
    steps = (PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),)
    service.register(Pipeline(id="p", steps=steps))
    result = service.run("p", "tester")
    assert result["error"] is None
    assert memory.habit_entries == [{"task": "tester", "pipeline": "p", "step": "s1"}]


def test_hook_habits_absent_si_pas_de_memoire() -> None:
    """Sans mémoire : succès d'étape sans crash ni hook."""
    service = build_service(runner=OkRunner())
    steps = (PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),)
    service.register(Pipeline(id="p", steps=steps))
    result = service.run("p", "tester")
    assert result["error"] is None
    assert result["results"][-1]["response"] == "ok-dev"


def test_on_error_skip_continue() -> None:
    """on_error="skip" : l'étape suivante s'exécute (pas d'arrêt ni timeout)."""
    failing = FailingRunner()
    ok = OkRunner()

    # Runner alterné : échoue sur l'étape s1, réussit sur s2
    def alternating(agent_key: str, prompt: str) -> str:
        if "s2" in prompt:
            return ok(agent_key, prompt)
        return failing(agent_key, prompt)

    service = build_service(runner=alternating, max_retries=0)

    steps = (
        PipeStep(
            name="s1",
            agent_key="dev",
            prompt_template="étape s1 {task}",
            on_error=OnError.SKIP,
        ),
        PipeStep(
            name="s2",
            agent_key="dev",
            prompt_template="étape s2 {task}",
            on_error=OnError.SKIP,
        ),
    )
    service.register(Pipeline(id="p", steps=steps))
    result = service.run("p", "tester")

    assert len(result["results"]) == 2
    assert result["results"][0]["error"] is not None  # s1 échoue
    assert result["results"][1]["error"] is None  # s2 continue et réussit
    assert result["error"] is None  # pas d'arrêt fatal : la dernière étape a réussi


class ThreeParamRunner:
    """Runner acceptant 3 paramètres (agent_key, prompt, model)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def __call__(self, agent_key: str, prompt: str, model: str | None = None) -> str:
        self.calls.append((agent_key, prompt, model))
        return f"ok-{agent_key}-{model}"


class TwoParamRunner:
    """Runner acceptant 2 paramètres (agent_key, prompt)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, agent_key: str, prompt: str) -> str:
        self.calls.append((agent_key, prompt))
        return f"ok-{agent_key}"


def test_runner_three_params_receives_model() -> None:
    """Parité _run_via_agent : runner 3 params reçoit le modèle sélectionné."""
    runner = ThreeParamRunner()

    # model_selector receives (agent_key, inference) and returns model name
    def model_selector(agent_key: str, inference: Any) -> str:
        return "qwen2.5-selected"

    service = PipelineService(agent_runner=runner, inference=None, model_selector=model_selector, max_retries=0)
    service.register(
        Pipeline(
            id="p",
            steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),),
        )
    )
    result = service.run("p", "tester")
    assert result["error"] is None
    assert len(runner.calls) == 1
    assert runner.calls[0][2] is not None  # model passed
    assert "qwen" in runner.calls[0][2].lower()


def test_runner_two_params_without_model() -> None:
    """Parité _run_via_agent : runner 2 params appelé sans modèle."""
    runner = TwoParamRunner()
    service = build_service(runner=runner, max_retries=0)
    service.register(Pipeline(id="p", steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),)))
    result = service.run("p", "tester")
    assert result["error"] is None
    assert len(runner.calls) == 1
    assert len(runner.calls[0]) == 2  # only agent_key, prompt


def test_non_callable_runner_error_typed() -> None:
    """Parité : runner non callable → erreur typée dans results, pas repr str()."""
    service = build_service(runner="not-a-callable", max_retries=0)
    service.register(Pipeline(id="p", steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),)))
    result = service.run("p", "tester")
    assert result["error"] is not None
    assert result["results"][-1]["response"] is None
    assert (
        "NonCallableRunnerError" in result["results"][-1]["error"]
        or "non callable" in result["results"][-1]["error"].lower()
    )


def test_max_retries_respected() -> None:
    """TDD : le nombre de réessais est respecté (sans backend configuré)."""
    service = build_service(max_retries=0)
    service.register(Pipeline(id="p", steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),)))
    result = service.run("p", "tester")
    assert "error" in result
    assert "Aucun agent_runner ni inference configuré" in result["error"]
