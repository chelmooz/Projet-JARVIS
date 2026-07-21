"""Validate UI state model against index.html.

Checks that every node selector, node trigger_selector, and edge trigger_selector
in ui-state-model.json has a corresponding element in index.html.
"""

import json
import re
import sys
from pathlib import Path


def load_model(path="static/ui-state-model.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def selectors_from_model(model):
    seen = set()
    for n in model["nodes"]:
        seen.add(n["selector"])
        seen.add(n["trigger_selector"])
    for e in model["edges"]:
        seen.add(e["trigger_selector"])
    return sorted(seen)


def selector_exists_in_html(selector, html):
    if selector.startswith("#"):
        frag = selector.lstrip("#").split(".")[0].split("[")[0].split(":")[0]
        return f'id="{frag}"' in html or f"id='{frag}'" in html
    if "[onclick" in selector:
        m = re.search(r'onclick=(["\'])([^"\']+)\1', selector)
        if m:
            return f'onclick={m.group(1)}{m.group(2)}{m.group(1)}' in html
    if "[data-tab" in selector:
        m = re.search(r'data-tab=(["\'])([^"\']+)\1', selector)
        if m:
            pat = f'data-tab={m.group(1)}{m.group(2)}{m.group(1)}'
            return pat in html
    # class-based — skip dynamic class lists like ".fb-drive, .fb-folder"
    # (these elements are generated at runtime by JS, not present in static HTML)
    if "," in selector:
        return True
    for part in selector.replace(",", " ").split():
        part = part.strip().lstrip(".").split("[")[0].split(":")[0]
        if part and part not in html:
            return False
    return True


def get_element_ids_from_js(js):
    """Extract every getElementById('...') id referenced in app.js."""
    return set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", js))


def validate(model, html):
    errors = []
    for sel in selectors_from_model(model):
        if not selector_exists_in_html(sel, html):
            errors.append(sel)
    return errors


def validate_js_ids(js, html):
    """Anti-regression B0 : every getElementById id in app.js must exist in HTML.

    IDs created dynamically at runtime (not present in static index.html) are allowed.
    """
    dynamic_ids = {"typing-indicator"}
    errors = []
    for eid in get_element_ids_from_js(js):
        if eid in dynamic_ids:
            continue
        if f'id="{eid}"' not in html and f"id='{eid}'" not in html:
            errors.append(eid)
    return errors


def main():
    root = Path(__file__).resolve().parent.parent
    model_path = root / "static" / "ui-state-model.json"
    html_path = root / "static" / "index.html"
    js_path = root / "static" / "assets" / "js" / "app.js"

    if not model_path.exists():
        print(f"ERROR: {model_path} not found")
        sys.exit(1)
    if not html_path.exists():
        print(f"ERROR: {html_path} not found")
        sys.exit(1)

    model = load_model(str(model_path))
    html = html_path.read_text("utf-8")
    errors = validate(model, html)

    if errors:
        print(f"FAIL: {len(errors)} selectors not found in index.html:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    js_ids_errors = []
    if js_path.exists():
        js = js_path.read_text("utf-8")
        js_ids_errors = validate_js_ids(js, html)
        if js_ids_errors:
            print(f"FAIL: {len(js_ids_errors)} getElementById ids in app.js missing from index.html:")
            for e in js_ids_errors:
                print(f"  - {e}")
            sys.exit(1)

    print(f"OK: all {len(selectors_from_model(model))} selectors found in index.html"
          + (f" + {len(get_element_ids_from_js(js))} JS ids checked" if js_path.exists() else ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
