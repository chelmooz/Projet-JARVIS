from pathlib import Path

from services.wiki_lint_service import WikiLintService


def _make_page(pages: Path, name: str, content: str) -> Path:
    page = pages / name
    page.write_text(content, encoding="utf-8")
    return page


def _valid_page_body(title: str) -> str:
    return (
        f'---\nid: T-x\ntitle: "{title}"\ntype: concept\n'
        f'agent: "@cyber"\n---\n\n# {title}\n\n## Résumé\nOK\n\n## Contenu\nOK\n'
    )


def test_lint_valid_page_returns_no_problems(tmp_path: Path) -> None:
    """Une page conforme au SCHEMA.md ne doit produire aucun problème."""
    pages = tmp_path / "wiki" / "pages" / "concepts"
    pages.mkdir(parents=True)
    page = _make_page(pages, "T-valid.md", _valid_page_body("Valid Technique"))

    service = WikiLintService(wiki_root=tmp_path / "wiki")
    assert service.lint_page(page) == []


def test_lint_detects_missing_frontmatter(tmp_path: Path) -> None:
    """Une page sans frontmatter doit être signalée."""
    pages = tmp_path / "wiki" / "pages" / "concepts"
    pages.mkdir(parents=True)
    page = _make_page(pages, "T-nofm.md", "# No frontmatter\n\nContent only.\n")

    service = WikiLintService(wiki_root=tmp_path / "wiki")
    assert "frontmatter:missing_start" in service.lint_page(page)


def test_lint_detects_uuid_title(tmp_path: Path) -> None:
    """Un titre resté un UUID STIX (échec d'extraction) doit être signalé."""
    pages = tmp_path / "wiki" / "pages" / "concepts"
    pages.mkdir(parents=True)
    page = _make_page(pages, "T-uuid.md", _valid_page_body("attack-pattern--abc123"))

    service = WikiLintService(wiki_root=tmp_path / "wiki")
    assert "title:is_uuid" in service.lint_page(page)


def test_lint_detects_unnormalized_agent(tmp_path: Path) -> None:
    """Un agent sans préfixe '@' doit être signalé."""
    pages = tmp_path / "wiki" / "pages" / "concepts"
    pages.mkdir(parents=True)
    body = '---\nid: T-x\ntitle: "Agent Test"\ntype: concept\nagent: "cyber"\n---\n\n# Agent Test\n\n## Résumé\nOK\n\n## Contenu\nOK\n'
    page = _make_page(pages, "T-agent.md", body)

    service = WikiLintService(wiki_root=tmp_path / "wiki")
    assert "agent:not_normalized" in service.lint_page(page)


def test_lint_detects_missing_section(tmp_path: Path) -> None:
    """Une section SCHEMA.md manquante doit être signalée."""
    pages = tmp_path / "wiki" / "pages" / "concepts"
    pages.mkdir(parents=True)
    body = '---\nid: T-x\ntitle: "No Section"\ntype: concept\nagent: "@cyber"\n---\n\n# No Section\n\n## Résumé\nOK\n'
    page = _make_page(pages, "T-nosec.md", body)

    service = WikiLintService(wiki_root=tmp_path / "wiki")
    assert "section:missing:Contenu" in service.lint_page(page)
