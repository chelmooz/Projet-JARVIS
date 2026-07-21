"""Add docstrings to functions/classes missing them, based on naming conventions."""
import ast
import os
import re

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIRS = ["services", "controllers", "agents", "graph", "scripts", "models", "config"]


def _doc_from_name(name, node):
    """ doc from name."""
    if isinstance(node, ast.ClassDef):
        return f"{name}."
    if name.startswith("__") and name.endswith("__"):
        return None if name in ("__init__",) else f"{name.strip('_').replace('_', ' ')}."
    desc = name.replace("_", " ")
    if desc.startswith("check "):
        desc = desc.replace("check ", "Verifie ")
    elif desc.startswith("get ") or desc.startswith("set "):
        desc = desc.replace("get ", "Recupere ").replace("set ", "Definit ")
    elif desc.startswith("is ") or desc.startswith("has "):
        desc = desc.replace("is ", "Indique si ").replace("has ", "Verifie si ")
    elif desc.startswith("run "):
        desc = desc.replace("run ", "Execute ")
    else:
        desc = desc.capitalize()
    return f"{desc}."


def process_file(path):
    """Process file."""
    with open(path, encoding="utf-8") as f:
        code = f.read()
    try:
        tree = ast.parse(code, filename=path)
    except SyntaxError:
        return False
    lines = code.splitlines()
    modified = False
    targets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and not ast.get_docstring(node):
                d = _doc_from_name(node.name, node)
                if d:
                    targets.append((node.lineno, d))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("__") and node.name.endswith("__") and \
               node.name not in ("__init__", "__call__", "__str__", "__repr__"):
                continue
            if not ast.get_docstring(node):
                d = _doc_from_name(node.name, node)
                if d:
                    targets.append((node.lineno, d))
    targets.sort(key=lambda x: -x[0])
    for lineno, doc in targets:
        idx = lineno - 1
        if idx >= len(lines):
            continue
        def_line = lines[idx].rstrip()
        # Skip multi-line function signatures (def ... (\n    ...)
        if def_line.endswith("(") or def_line.endswith(","):
            continue
        # Check if already has docstring
        next_idx = idx + 1
        while next_idx < len(lines) and not lines[next_idx].strip():
            next_idx += 1
        if next_idx < len(lines) and lines[next_idx].strip().startswith(('"""', "'''")):
            continue
        indent = re.match(r"^(\s*)", lines[idx]).group(1)
        body_indent = indent + "    "
        doc_line = f'{body_indent}"""{doc}"""'
        lines.insert(next_idx, doc_line)
        modified = True
    if modified:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return modified


def main():
    """Main."""
    count = 0
    for d in SOURCE_DIRS:
        root = os.path.join(PROJECT, d)
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                fp = os.path.join(dirpath, fn)
                if process_file(fp):
                    rel = os.path.relpath(fp, PROJECT)
                    print(f"  Docstring ajoutee: {rel}")
                    count += 1
    print(f"\nFichiers modifies: {count}")


if __name__ == "__main__":
    main()
