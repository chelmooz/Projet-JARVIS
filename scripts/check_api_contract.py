"""Contract testing helpers: extract frontend fetch() calls and backend routes.

Usage:
    from scripts.check_api_contract import extract_frontend_calls, extract_backend_routes
"""
import os
import re

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")


def _find_closing_paren(text: str, start: int) -> int:
    """Find the matching closing parenthesis from position start (which is after '(')."""
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        i += 1
    return i - 1 if depth == 0 else len(text)


def extract_frontend_calls(html_text: str | None = None) -> set[tuple[str, str]]:
    """Extract (method, path) tuples from fetch() calls in frontend HTML.

    Defaults to reading static/index.html. GET is assumed when no method
    is specified in the fetch() options object.
    """
    if html_text is None:
        index_path = INDEX_HTML
        if not os.path.exists(index_path):
            return set()
        with open(index_path, encoding="utf-8") as f:
            html_text = f.read()

    results: set[tuple[str, str]] = set()

    # Find each fetch( ... ) call with balanced parens
    start = 0
    while True:
        idx = html_text.find("fetch(", start)
        if idx == -1:
            break
        paren_start = idx + 6  # skip "fetch("
        paren_end = _find_closing_paren(html_text, paren_start)
        call_text = html_text[paren_start:paren_end]

        # Extract URL path (first string argument)
        path_m = re.search(r"['\"]([^'\"]+)['\"]", call_text)
        if not path_m:
            start = idx + 1
            continue
        path = path_m.group(1)

        # Detect HTTP method from options object inside the call
        method = "GET"
        method_m = re.search(r"method\s*:\s*['\"](\w+)['\"]", call_text)
        if method_m:
            method = method_m.group(1).upper()

        results.add((method, path.rstrip("/")))
        start = paren_end + 1

    return results


def extract_backend_routes(app) -> set[tuple[str, str]]:
    """Extract (method, path) tuples from a FastAPI app's registered routes.

    Excludes automatic routes (/openapi.json, /docs, /redoc) and
    static file mounts.
    """
    skip_prefixes = ("/openapi.json", "/docs", "/redoc")
    skip_methods = ("HEAD", "OPTIONS")

    results: set[tuple[str, str]] = set()
    for route in app.routes:
        # Skip non-API routes (static mounts, etc.)
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        if any(route.path.startswith(p) for p in skip_prefixes):
            continue

        for method in route.methods:
            if method in skip_methods:
                continue
            results.add((method, route.path.rstrip("/")))

    return results


def compute_drift(frontend: set[tuple[str, str]], backend: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Return calls that exist in frontend but not in backend (drift)."""
    return frontend - backend
