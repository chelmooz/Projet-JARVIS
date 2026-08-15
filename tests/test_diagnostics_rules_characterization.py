from __future__ import annotations

from services.diagnostics.rules import (
    Severity,
    _first,
    _pick,
    _plural,
    _port_short_name,
    _tag,
    compute_verdict,
    generate_recommendations,
)


def base_results(
    ram: float = 16, gpu: bool = True, missing: list[str] | None = None, internet: bool = True, free: float = 10
) -> dict:
    return {
        "ram": {"total_gb": ram},
        "gpu": {"detected": gpu, "detail": "GPU"},
        "python": {"missing_deps": missing or [], "venv_ok": True, "python_env_ok": True},
        "network": {"internet": internet, "ports": {"11436": "in_use", "8000": "free", "3000": "free"}},
        "disk": {"free_gb": free},
        "binaries": [
            {"name": "ollama", "path": "/bin/ollama", "exists": True},
            {"name": "other", "path": None, "exists": False},
        ],
    }


def test_small_ram_gpu_missing_dependencies_and_verdict() -> None:
    recommendations = generate_recommendations(
        base_results(ram=4, gpu=False, missing=["httpx"], internet=False, free=2)
    )
    assert any("RAM" in rec and rec.startswith("[FAIL]") for rec in recommendations)
    assert any("GPU" in rec and rec.startswith("[WARN]") for rec in recommendations)
    assert compute_verdict(recommendations).startswith("FAIL")


def test_threshold_warning_and_ok_paths() -> None:
    warning = generate_recommendations(base_results(ram=12))
    assert any("modèles lourds" in rec for rec in warning)
    ok = generate_recommendations(base_results(ram=32))
    assert any("suffisant" in rec for rec in ok)


def test_python_env_network_disk_and_binary_recommendations() -> None:
    results = base_results()
    results["python"] = {"missing_deps": [], "venv_ok": False, "python_env_ok": False}
    results["network"]["internet"] = False
    results["disk"]["free_gb"] = 3
    recommendations = generate_recommendations(results)
    assert any("venv non trouvé" in rec for rec in recommendations)
    assert any("non accessible" in rec for rec in recommendations)
    assert any("insuffisant" in rec for rec in recommendations)
    assert any("introuvable" in rec for rec in recommendations)


def test_port_recommendations_and_helpers() -> None:
    recommendations = generate_recommendations(base_results())
    assert any("Port 11436 (Ollama)" in rec and "occupé" in rec for rec in recommendations)
    assert any("Port 8000 (API)" in rec and "libre" in rec for rec in recommendations)
    assert _port_short_name(9999) == "9999"
    assert _tag(Severity.INFO, "msg") == "[INFO] msg"
    assert _pick(True, "a", "b") == "a"
    assert _pick(False, "a", "b") == "b"
    assert _plural(1) == ""
    assert _plural(2) == "s"


def test_first_and_verdict_pluralization() -> None:
    rules = [(lambda r: r["yes"], Severity.OK, lambda r: "done")]
    assert _first(rules, {"yes": True}) == "[OK]   done"
    assert _first(rules, {"yes": False}) == ""
    assert compute_verdict(["[WARN] one", "[WARN] two"]) == "WARNING (2 avertissements)"
    assert compute_verdict([]) == "OK"
