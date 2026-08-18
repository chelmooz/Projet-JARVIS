"""Tests for Wiki LLM compilation (MT-KB-L3g)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.wiki_ingest_service import WikiIngestService
from services.wiki_lint_service import WikiLintService
from tests.conftest import FakeInference


def test_compile_entry_produces_valid_markdown(tmp_path: Path) -> None:
    """compile_entry(entry, FakeInference) -> markdown conforme SCHEMA.md."""
    entry = {
        "id": "T1059",
        "agent": "@cyber",
        "source": "mitre-attack.jsonl",
        "text": "Adversaries may abuse command and script interpreters to execute commands.",
        "metadata": {"name": "Command and Scripting Interpreter", "type": "technique"},
    }
    service = WikiIngestService(wiki_root=tmp_path / "wiki")
    inference = FakeInference(
        response="# Compiled Title\n\n## Résumé\nCompiled summary.\n\n## Contenu\nCompiled content.\n\n## Liens\n- [[T1000]] - Related technique.\n\n## Sources\n- `mitre-attack.jsonl#T1059`"
    )

    markdown = service.compile_entry(entry, inference)

    # Frontmatter présent et bien délimité
    assert markdown.startswith("---\n"), "Le markdown doit commencer par ---"
    assert "\n---\n\n" in markdown, "Le frontmatter doit se terminer par --- suivi d'une ligne vide"

    # Sections SCHEMA.md présentes
    assert "## Résumé" in markdown, "Section Résumé manquante"
    assert "## Contenu" in markdown, "Section Contenu manquante"
    assert "## Liens" in markdown, "Section Liens manquante"
    assert "## Sources" in markdown, "Section Sources manquante"

    # Frontmatter contient les bonnes clés YAML
    assert "id: T1059" in markdown, "Clé id manquante dans frontmatter"
    assert 'agent: "@cyber"' in markdown, "Clé agent manquante dans frontmatter"
    assert "type: concept" in markdown, "Clé type manquante dans frontmatter"

    # Lint doit passer (validation SCHEMA.md)
    page_path = tmp_path / "wiki" / "pages" / "concepts" / "T1059.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(markdown, encoding="utf-8")
    linter = WikiLintService(wiki_root=tmp_path / "wiki")
    problems = linter.lint_page(page_path)
    assert problems == [], f"Lint a trouvé des problèmes: {problems}"


def test_compile_entry_adds_wikilinks(tmp_path: Path) -> None:
    """compile_entry ajoute des wikilinks [[...]] via metadata.mitre_technique_ids ou source partagé."""
    entry = {
        "id": "T1059",
        "agent": "@cyber",
        "source": "mitre-attack.jsonl",
        "text": "Command and Scripting Interpreter: Adversaries may abuse interpreters.",
        "metadata": {
            "name": "Command and Scripting Interpreter",
            "mitre_technique_ids": ["T1059.001", "T1059.003", "T1000"],
        },
    }
    service = WikiIngestService(wiki_root=tmp_path / "wiki")
    # FakeInference qui inclut des wikilinks vers les techniques MITRE
    inference = FakeInference(
        response="# Compiled\n\n## Résumé\nSummary.\n\n## Contenu\nContent.\n\n## Liens\n- [[T1059.001]] - Sub-technique\n- [[T1059.003]] - Sub-technique\n- [[T1000]] - Related\n\n## Sources\n- `mitre-attack.jsonl#T1059`"
    )

    markdown = service.compile_entry(entry, inference)

    # Vérifie la présence de wikilinks dans la section Liens
    assert "[[T1059.001]]" in markdown or "[[T1059.003]]" in markdown or "[[T1000]]" in markdown, "Wikilinks manquants"
    assert "## Liens" in markdown, "Section Liens manquante"


def test_compile_batch_regenerates_index(tmp_path: Path) -> None:
    """compile_batch(entries) régénère wiki/pages/index.md avec liens [[<id>]] vers toutes les pages."""
    entries = [
        {
            "id": "T1059",
            "agent": "@cyber",
            "source": "mitre-attack.jsonl",
            "text": "Technique 1: description.",
            "metadata": {"name": "Technique 1"},
        },
        {
            "id": "T1000",
            "agent": "@cyber",
            "source": "mitre-attack.jsonl",
            "text": "Technique 2: description.",
            "metadata": {"name": "Technique 2"},
        },
    ]
    service = WikiIngestService(wiki_root=tmp_path / "wiki")
    inference = FakeInference(
        response="# Compiled\n\n## Résumé\nSummary.\n\n## Contenu\nContent.\n\n## Liens\n\n## Sources\n"
    )

    service.compile_batch(entries, inference)

    # index.md doit exister
    index_path = tmp_path / "wiki" / "pages" / "index.md"
    assert index_path.exists(), "index.md non généré"

    content = index_path.read_text(encoding="utf-8")
    # Doit contenir des liens wikilinks vers les pages
    assert "[[T1059]]" in content, "Lien vers T1059 manquant dans index.md"
    assert "[[T1000]]" in content, "Lien vers T1000 manquant dans index.md"


def test_compile_fallback_deterministic_if_no_inference(tmp_path: Path) -> None:
    """inference=None -> fallback déterministe (texte brut + frontmatter), pas de crash."""
    entry = {
        "id": "T1059",
        "agent": "@cyber",
        "source": "mitre-attack.jsonl",
        "text": "Adversaries may abuse command and script interpreters to execute commands.",
        "metadata": {"name": "Command and Scripting Interpreter", "type": "technique"},
    }
    service = WikiIngestService(wiki_root=tmp_path / "wiki")

    # Sans inference -> fallback (comportement Phase 1 préservé)
    markdown = service.compile_entry(entry, None)

    # Doit produire un markdown valide (frontmatter + sections de base)
    assert markdown.startswith("---\n"), "Le markdown doit commencer par ---"
    assert "\n---\n\n" in markdown, "Le frontmatter doit se terminer par ---"
    assert "id: T1059" in markdown, "Clé id manquante dans frontmatter"
    assert 'agent: "@cyber"' in markdown, "Clé agent manquante dans frontmatter"
    assert "type: concept" in markdown, "Clé type manquante dans frontmatter"
    assert "## Résumé" in markdown, "Section Résumé manquante"
    assert "## Contenu" in markdown, "Section Contenu manquante"
    assert "## Liens" in markdown, "Section Liens manquante"
    assert "## Sources" in markdown, "Section Sources manquante"

    # Lint doit passer
    page_path = tmp_path / "wiki" / "pages" / "concepts" / "T1059.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(markdown, encoding="utf-8")
    linter = WikiLintService(wiki_root=tmp_path / "wiki")
    problems = linter.lint_page(page_path)
    assert problems == [], f"Lint a trouvé des problèmes: {problems}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
