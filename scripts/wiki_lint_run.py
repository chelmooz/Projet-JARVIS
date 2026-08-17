"""MT-KB-L1e — Lint des pages wiki (script temporaire, non commité)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.wiki_lint_service import WikiLintService  # noqa: E402


def main() -> None:
    service = WikiLintService()
    issues = service.lint_all()
    if not issues:
        print("LINT OK : toutes les pages sont conformes au SCHEMA.md")
    else:
        print(f"LINT KO : {len(issues)} page(s) non conforme(s)")
        for name, problems in issues:
            print(f"  {name}: {problems}")


if __name__ == "__main__":
    main()
