from __future__ import annotations

import ast

from services import analysis_core as core


def test_node_name_and_call_name() -> None:
    function = ast.parse("def f():\n    pass").body[0]
    assert core._node_name(function) == "f"
    assert core._node_name(ast.Pass()) == "Pass"
    assert core._get_call_name(ast.parse("obj.run()", mode="eval").body) == "run"
    assert core._get_call_name(ast.parse("run()", mode="eval").body) == "run"
    assert core._get_call_name(ast.parse("factories[0]()", mode="eval").body) == ""


def test_max_nest_depth_skips_nested_functions_and_classes() -> None:
    tree = ast.parse(
        "def outer():\n    if x:\n        for y in xs:\n            pass\n    def inner():\n        if z:\n            pass\n"
    )
    assert core._max_nest_depth(tree.body[0]) == 2


def test_has_early_return_handles_control_flow() -> None:
    assert core._has_early_return(ast.parse("return 1").body) is True
    assert core._has_early_return(ast.parse("if x:\n    raise ValueError()\n").body) is True
    assert core._has_early_return(ast.parse("x = 1").body) is False


def test_py_files_skips_directories_and_count_lines(tmp_path) -> None:
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    skipped = tmp_path / "venv"
    skipped.mkdir()
    (skipped / "b.py").write_text("x\n", encoding="utf-8")
    assert core._py_files(str(tmp_path)) == [str(tmp_path / "a.py")]
    assert core._count_lines(str(tmp_path / "a.py")) == 1
    assert core._count_lines(str(tmp_path / "missing.py")) == 0


def test_resolve_test_candidates_for_services_and_fallback(tmp_path) -> None:
    source = str(tmp_path / "services" / "sample.py")
    candidates = core._resolve_test_candidates(source)
    assert any("tests" in candidate for candidate in candidates)
    fallback = core._resolve_test_candidates(str(tmp_path / "other.py"))
    assert core.os.path.basename(fallback[-2]) == "test_other.py"
    assert core.os.path.basename(fallback[-1]) == "other_test.py"
    assert core.os.path.basename(core.os.path.dirname(fallback[-2])) == "tests"
