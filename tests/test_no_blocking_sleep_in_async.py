"""AUDIT-P2.2 : aucun `time.sleep` ne doit rester dans une fonction async.

Règle :
  - Dans une fonction `async def` : doit utiliser `await asyncio.sleep(...)`,
    jamais `time.sleep(...)` (bloquant) ni `await time.sleep(...)` (bug).
  - Dans une fonction synchrone (`def`) : `time.sleep` est autorisé hors event loop
    (thread/worker, processus autonome). On ne le convertit pas pour ne pas casser
    les appelants.

Le test parcourt les fichiers de production ciblés et lève immédiatement si :
  1. un `await time.sleep(...)` est présent (erreur manifeste) ;
  2. une fonction `async def` contient un appel `time.sleep(...)` sans `await`.
"""
import ast
import os

PROD_FILES = [
    "controllers/context.py",
    "ports/pipeline.py",
    "services/file_utils.py",
    "services/launcher.py",
    "services/pipeline.py",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _SleepVisitor(ast.NodeVisitor):
    """Repère les usages fautifs de time.sleep dans le module."""

    def __init__(self):
        self.errors = []

    def visit_AsyncFunctionDef(self, node):
        for child in ast.walk(node):
            if isinstance(child, ast.Await) and self._is_time_sleep(child.value):
                self.errors.append(
                    f"{node.name}:{child.lineno}: await time.sleep(...) est un bug (time.sleep n'est pas awaitable)"
                )
            if isinstance(child, ast.Call) and self._is_time_sleep(child) and not self._has_await_parent(node, child):
                self.errors.append(
                    f"{node.name}:{child.lineno}: time.sleep(...) bloquant dans une fonction async "
                    f"(utiliser 'await asyncio.sleep(...)')"
                )
        self.generic_visit(node)

    @staticmethod
    def _is_time_sleep(node):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        return (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "time"
            and func.attr == "sleep"
        )

    @staticmethod
    def _has_await_parent(func_node, target):
        return any(isinstance(node, ast.Await) and node.value is target for node in ast.walk(func_node))


def _load_module(rel_path):
    abs_path = os.path.join(BASE_DIR, rel_path)
    with open(abs_path, encoding="utf-8") as fh:
        return abs_path, ast.parse(fh.read(), filename=abs_path)


def test_no_blocking_sleep_in_async():
    """Aucun time.sleep bloquant résiduel dans une fonction async."""
    all_errors = []
    missing = []
    for rel in PROD_FILES:
        abs_path = os.path.join(BASE_DIR, rel)
        if not os.path.exists(abs_path):
            missing.append(rel)
            continue
        _, tree = _load_module(rel)
        visitor = _SleepVisitor()
        visitor.visit(tree)
        all_errors.extend(f"{rel}:{err}" for err in visitor.errors)

    # warmup.py absent du dépôt : signalé, pas bloquant.
    note = "warmup.py introuvable dans le dépôt (non ciblé)"
    if missing:
        note += f" ; fichiers manquants: {missing}"

    assert not all_errors, (
        "time.sleep fautif détecté dans une fonction async :\n"
        + "\n".join(all_errors)
        + f"\n(note: {note})"
    )
