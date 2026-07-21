"""OpenAPI contract helpers: extract schemas and frontend payload keys.

Usage:
    from scripts.check_openapi_contract import get_route_schemas, extract_frontend_payload_keys
"""
import os
import re

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")


def get_route_schemas(app) -> dict[tuple[str, str], dict]:
    """Extract (method, path) -> {schema_name, required, properties} from app.openapi().

    Only returns routes with a JSON request body (POST, PUT).
    """
    spec = app.openapi()
    schemas_def = spec.get("components", {}).get("schemas", {})

    result: dict[tuple[str, str], dict] = {}
    for path, methods in spec.get("paths", {}).items():
        for method, detail in methods.items():
            if method.upper() not in ("POST", "PUT"):
                continue
            rb = detail.get("requestBody", {})
            ct = rb.get("content", {})
            sr = ct.get("application/json", {}).get("schema", {})
            ref = sr.get("$ref", "")
            schema_name = ref.split("/")[-1] if ref else "inline"

            if schema_name and schema_name in schemas_def:
                schema = schemas_def[schema_name]
                result[(method.upper(), path.rstrip("/"))] = {
                    "schema_name": schema_name,
                    "required": schema.get("required", []),
                    "properties": list(schema.get("properties", {}).keys()),
                }
            else:
                result[(method.upper(), path.rstrip("/"))] = {
                    "schema_name": schema_name,
                    "required": [],
                    "properties": [],
                }
    return result


def extract_frontend_payload_keys(html_text: str | None = None) -> dict[str, set[str]]:
    """Extract JSON.stringify keys per fetch path from frontend HTML.

    Returns dict: path -> set of keys (e.g. {"/api/jarvis": {"task", "image", "conversation_id"}})
    """
    if html_text is None:
        index_path = INDEX_HTML
        if not os.path.exists(index_path):
            return {}
        with open(index_path, encoding="utf-8") as f:
            html_text = f.read()

    result: dict[str, set[str]] = {}

    # Strategy: for each fetch() call, look for JSON.stringify in its context
    # Find all fetch(...) calls with balanced parens
    start = 0
    while True:
        idx = html_text.find("fetch(", start)
        if idx == -1:
            break
        # Extract URL
        url_m = re.search(r"fetch\s*\(\s*['\"]([^'\"]+)['\"]", html_text[idx:])
        if not url_m:
            start = idx + 1
            continue
        path = url_m.group(1).rstrip("/")

        # Find the actual position of the fetch call body
        actual_start = html_text.index("(", idx) + 1
        depth = 1
        i = actual_start
        while i < len(html_text) and depth > 0:
            if html_text[i] == "(":
                depth += 1
            elif html_text[i] == ")":
                depth -= 1
            i += 1
        call_text = html_text[actual_start:i - 1] if depth == 0 else html_text[actual_start:]

        # Find JSON.stringify in the call context (within 300 chars after fetch URL)
        stringify_m = re.search(
            r"JSON\.stringify\s*\(\s*(\{[^}]*\}|[^)]+)\s*\)", call_text
        )
        if not stringify_m:
            start = idx + 1
            continue

        inner = stringify_m.group(1)
        # Extract keys: look for patterns like `key:` or `{key}` before `:`
        # This handles: { backend }, { task, image }, { profile, model }, { key: 'offline', value }
        keys: set[str] = set()
        # Match key identifiers: word chars before ':' or spread `{var}` where var is the key
        # Pattern 1: { profile, model } -> shortest form
        # Pattern 2: { key: 'offline', value: checked }
        # Pattern 3: { image: e.target.result, task: '...' }
        key_matches = re.findall(r"(\w+)\s*:", inner)
        if key_matches:
            keys.update(key_matches)
        else:
            # No colons -> spread variables like { backend } or {path}
            # Extract bare identifiers
            bare = re.findall(r"\b([a-zA-Z_]\w*)\b", inner)
            # Filter out common JS keywords
            skip = {"null", "undefined", "true", "false", "JSON", "stringify"}
            keys.update(k for k in bare if k not in skip)

        if keys:
            if path not in result:
                result[path] = set()
            result[path].update(keys)
        start = idx + 1

    return result


def check_required_fields(
    route_schemas: dict[tuple[str, str], dict],
    frontend_payloads: dict[str, set[str]],
) -> list[dict]:
    """Compare frontend payload keys against required schema fields.

    Returns list of mismatches: [{route, schema_name, missing_fields}]
    """
    issues = []
    for (method, path), schema in route_schemas.items():
        required = set(schema["required"])
        if not required:
            continue
        fe_keys = frontend_payloads.get(path, set())
        missing = required - fe_keys
        if missing:
            issues.append({
                "route": f"{method} {path}",
                "schema_name": schema["schema_name"],
                "missing_fields": sorted(missing),
            })
    return issues
