from pathlib import Path

WIKI_ROOT = Path("wiki")


def test_wiki_pages_directories_exist() -> None:
    """Vérifie que les dossiers concepts/skills/procedures existent."""
    for subdir in ["concepts", "skills", "procedures"]:
        path = WIKI_ROOT / "pages" / subdir
        assert path.exists(), f"Le dossier {path} n'existe pas"
        assert path.is_dir(), f"{path} n'est pas un dossier"


def test_schema_md_exists_and_has_sections() -> None:
    """Vérifie que SCHEMA.md existe et contient les sections obligatoires."""
    schema_path = WIKI_ROOT / "SCHEMA.md"
    assert schema_path.exists(), "wiki/SCHEMA.md n'existe pas"
    content = schema_path.read_text(encoding="utf-8")

    # Sections obligatoires selon Karpathy LLM Wiki
    required_sections = ["Frontmatter", "Titre", "Résumé", "Contenu", "Liens", "Sources"]
    for section in required_sections:
        assert section in content, f"Section '{section}' manquante dans SCHEMA.md"


def test_schema_md_defines_frontmatter_yaml() -> None:
    """Vérifie que SCHEMA.md spécifie bien le format YAML pour le frontmatter."""
    content = (WIKI_ROOT / "SCHEMA.md").read_text(encoding="utf-8")
    # Doit contenir les clés YAML obligatoires pour le graphe
    required_keys = ["id:", "title:", "type:", "links_to:"]
    for key in required_keys:
        assert key in content, f"Clé frontmatter '{key}' manquante dans SCHEMA.md"


def test_log_md_exists() -> None:
    """Vérifie que log.md existe pour tracer les ingests."""
    log_path = WIKI_ROOT / "log.md"
    assert log_path.exists(), "wiki/log.md n'existe pas"
    content = log_path.read_text(encoding="utf-8")
    assert "Ingest" in content or "Journal" in content, "log.md doit avoir un titre"
