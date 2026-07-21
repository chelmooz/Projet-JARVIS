"""Analysis core — constantes et helpers partagés par les analyseurs statiques.

Module sans dépendance vers les autres modules d'analyse (évite les imports
circulaires) : il ne contient que des constantes, des regex et des fonctions
pures sur l'AST / le système de fichiers.
"""
import ast
import os
import re

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SOURCE_DIRS = [
    os.path.join(_PROJECT_ROOT, "services"),
    os.path.join(_PROJECT_ROOT, "controllers"),
    os.path.join(_PROJECT_ROOT, "agents"),
    os.path.join(_PROJECT_ROOT, "graph"),
    os.path.join(_PROJECT_ROOT, "scripts"),
    os.path.join(_PROJECT_ROOT, "models"),
    os.path.join(_PROJECT_ROOT, "config"),
]
_TEST_DIR = os.path.join(_PROJECT_ROOT, "tests")
_SKIPPED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".pytest-temp",
    ".ruff_cache",
    "__pycache__",
    "bin",
    "lib",
    "logs",
    "memory",
    "models",
    "node_modules",
    "portable_python",
    "venv",
}
_MAX_PROJECT_FILES = 500

_MAX_CYCLOMATIC = 10
_MAX_DUPLICATE_LINES = 3
_MAX_NESTED_LOOPS = 2
_MAX_BRANCHES = 8
_MAX_FUNC_LINES = 20
_MAX_PARAMS = 3
_MAX_NESTING = 3
_MAX_CLASS_LINES = 150
_MAX_FILE_LINES = 500

_WEIGHTS = {"code_quality": 0.40, "tests": 0.30, "structure": 0.15, "documentation": 0.15}

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|secret|api_key|apikey|token|aws_secret_access_key)\s*[:=]\s*[\"']"), "hardcoded_secret"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_key"),
    (re.compile(r"\bgh[ous]_[0-9a-zA-Z]{36}\b"), "github_token"),
    (re.compile(r"\bsk-[0-9a-zA-Z]{20,48}\b"), "openai_key"),
    (re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}(?:\.[a-zA-Z0-9_-]{10,}){2}\b"), "jwt_token"),
    (re.compile(r"-----BEGIN[^ ]+PRIVATE KEY-----"), "private_key"),
]
_SQL_INJECTION = re.compile(r"(?i)(execute|executemany|raw_input|input)\s*\(\s*f['\"]|%\s*\(|\.format\(.*[\"']\s*\+|[\"']\s*\+.*[\"']\s*[)]")
_PATH_TRAVERSAL = re.compile(r"(?i)(open|read|write|remove|unlink|rmdir|shutil)\s*\(\s*.*(?:request\.get|request\.post|request\.form|request\.args|input\s*\(|sys\.argv)")
_EVAL_USAGE = re.compile(r"(?<![.\w])(eval|exec|compile|__import__)\s*\(")
_PICKLE_USAGE = re.compile(r"\b(pickle\.loads|pickle\.load|yaml\.load\s*\(|marshal\.load)\b")
_XSS_RISK = re.compile(r"(?i)(innerHTML|outerHTML|document\.write|response\.write|\.html\s*=\s*.*[\"']\s*\+)")
_NAKED_EXCEPT = re.compile(r"^\s*except\s*:")

_TEST_DIR_FRAGMENTS = (
    f"{os.sep}src{os.sep}",
    f"{os.sep}services{os.sep}",
    f"{os.sep}controllers{os.sep}",
)


def _node_name(node) -> str:
    return node.name if hasattr(node, "name") else type(node).__name__


def _max_nest_depth(node: ast.AST, depth: int = 0) -> int:
    max_d = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith)):
            max_d = max(max_d, _max_nest_depth(child, depth + 1))
        elif not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            max_d = max(max_d, _max_nest_depth(child, depth))
    return max_d


def _has_early_return(nodes: list) -> bool:
    for stmt in nodes:
        if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        if isinstance(stmt, ast.If) and (_has_early_return(stmt.body) or _has_early_return(stmt.orelse)):
                return True
    return False


def _py_files(root: str) -> list[str]:
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIPPED_DIR_NAMES]
        for fn in filenames:
            if fn.endswith(".py"):
                result.append(os.path.join(dirpath, fn))
    return sorted(result)


def _count_lines(path: str) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return len(f.readlines())
    except OSError:
        return 0


def _get_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _resolve_test_candidates(source_path: str) -> list[str]:
    """Candidats de fichiers de test pour `source_path`.

    Fusionne les deux anciennes implémentations (I7) : `_check_testing`
    et `check_test_exists` calculaient les mêmes chemins.
    """
    dir_name = os.path.dirname(source_path)
    file_name = os.path.basename(source_path)
    candidates = []
    for frag in _TEST_DIR_FRAGMENTS:
        if frag in source_path:
            candidates.append(source_path.replace(frag, f"{os.sep}tests{os.sep}"))
    candidates.append(os.path.join(dir_name, "tests", f"test_{file_name}"))
    candidates.append(os.path.join(dir_name, "tests", file_name.replace(".py", "_test.py")))
    return candidates
