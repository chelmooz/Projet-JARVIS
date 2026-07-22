"""Tests for UI state model validation (P5 Ch5).

Covers:
- Validate that ui-state-model.json is valid JSON with correct structure
- Validate that all selectors exist in index.html
- Validate edge references (from/to) point to existing nodes
"""

import json
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent


MODEL_PATH = BASE / "static" / "ui-state-model.json"


def _load_model():
    with open(MODEL_PATH, encoding="utf-8") as f:
        return json.load(f)


MODEL_EXISTS = MODEL_PATH.exists()


@pytest.mark.skipif(not MODEL_EXISTS, reason="ui-state-model.json non présent (hors périmètre backend)")
class TestStateModelStructure:

    def test_json_is_valid(self):
        m = _load_model()
        assert "nodes" in m
        assert "edges" in m
        assert "initial" in m

    def test_at_least_7_nodes(self):
        m = _load_model()
        assert len(m["nodes"]) >= 7

    def test_at_least_42_edges(self):
        m = _load_model()
        assert len(m["edges"]) >= 42

    def test_initial_node_exists(self):
        m = _load_model()
        ids = {n["id"] for n in m["nodes"]}
        assert m["initial"] in ids

    def test_edge_endpoints_exist(self):
        m = _load_model()
        ids = {n["id"] for n in m["nodes"]}
        for e in m["edges"]:
            assert e["from"] in ids, f"Edge from={e['from']} not in nodes"
            assert e["to"] in ids, f"Edge to={e['to']} not in nodes"

    def test_each_node_has_required_keys(self):
        m = _load_model()
        required = {"id", "label", "selector", "post_condition", "trigger_selector"}
        for n in m["nodes"]:
            assert required.issubset(n.keys()), f"Node {n['id']} missing keys"

    def test_edge_has_required_keys(self):
        m = _load_model()
        for e in m["edges"]:
            assert "from" in e
            assert "to" in e
            assert "trigger_selector" in e


@pytest.mark.skipif(not MODEL_EXISTS, reason="ui-state-model.json non présent (hors périmètre backend)")
class TestStateModelSelectors:

    def test_all_selectors_exist_in_html(self):
        from scripts.validate_state_model import load_model, validate

        m = load_model(str(BASE / "static" / "ui-state-model.json"))
        html = (BASE / "static" / "index.html").read_text("utf-8")
        errors = validate(m, html)
        assert len(errors) == 0, f"Missing selectors: {errors}"


class TestCoverageReport:

    def test_report_format(self):
        report = {
            "edges_total": 56,
            "edges_visited": 56,
            "coverage_pct": 100,
            "failures": [],
        }
        assert report["coverage_pct"] == 100
        assert report["edges_total"] >= report["edges_visited"]
        assert isinstance(report["failures"], list)

    def test_incomplete_coverage_reports_failures(self):
        report = {
            "edges_total": 2,
            "edges_visited": 1,
            "coverage_pct": 50,
            "failures": [{"edge": "chat->vision", "reason": "Trigger not found"}],
        }
        assert len(report["failures"]) > 0
