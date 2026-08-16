from pathlib import Path

from services.wiki_ingest_service import WikiIngestService


def test_ingest_entry_generates_valid_markdown() -> None:
    """Une entrée JSONL doit produire un markdown avec frontmatter valide."""
    entry = {
        "id": "T1059",
        "agent": "@cyber",
        "source": "mitre-attack.jsonl",
        "text": "Adversaries may abuse command and script interpreters to execute commands.",
        "metadata": {"name": "Command and Scripting Interpreter", "type": "technique"},
    }
    service = WikiIngestService()
    markdown = service.ingest_entry(entry)

    # Frontmatter présent et bien délimité
    assert markdown.startswith("---\n"), "Le markdown doit commencer par ---"
    assert "---\n\n" in markdown, "Le frontmatter doit se terminer par --- suivi d'une ligne vide"

    # Sections SCHEMA.md présentes
    assert "# Command and Scripting Interpreter" in markdown, "Titre H1 manquant"
    assert "## Résumé" in markdown or "## Contenu" in markdown, "Section Résumé ou Contenu manquante"

    # Frontmatter contient les bonnes clés YAML
    assert "id: T1059" in markdown, "Clé id manquante dans frontmatter"
    assert 'agent: "@cyber"' in markdown, "Clé agent manquante dans frontmatter"
    assert "type: concept" in markdown, "Clé type manquante dans frontmatter"


def test_ingest_entry_to_file_creates_file() -> None:
    """ingest_entry_to_file doit créer un fichier dans wiki/pages/concepts/."""
    entry = {
        "id": "T1059-test",
        "agent": "@cyber",
        "source": "mitre-attack.jsonl",
        "text": "Test description for unit test.",
        "metadata": {"name": "Test Technique"},
    }
    service = WikiIngestService()

    # Cleanup si existe déjà
    test_file = Path("wiki/pages/concepts/T1059-test.md")
    if test_file.exists():
        test_file.unlink()

    file_path = service.ingest_entry_to_file(entry)

    assert file_path.exists(), f"Le fichier {file_path} n'a pas été créé"
    assert file_path.as_posix() == "wiki/pages/concepts/T1059-test.md", "Mauvais chemin de fichier"

    # Vérifie le contenu
    content = file_path.read_text(encoding="utf-8")
    assert "id: T1059-test" in content, "ID manquant dans le fichier créé"

    # Cleanup
    file_path.unlink()


def test_ingest_batch_processes_multiple_entries() -> None:
    """ingest_batch doit traiter plusieurs entrées et retourner les chemins."""
    entries = [
        {
            "id": f"T100{i}",
            "agent": "@cyber",
            "source": "mitre-attack.jsonl",
            "text": f"Description for technique {i}.",
            "metadata": {"name": f"Technique {i}"},
        }
        for i in range(3)
    ]
    service = WikiIngestService()

    # Cleanup
    for i in range(3):
        test_file = Path(f"wiki/pages/concepts/T100{i}.md")
        if test_file.exists():
            test_file.unlink()

    paths = service.ingest_batch(entries, max_entries=3)

    assert len(paths) == 3, f"Attendu 3 chemins, reçu {len(paths)}"
    assert all(p.exists() for p in paths), "Tous les fichiers doivent exister"

    # Cleanup
    for path in paths:
        path.unlink()


def test_title_extracted_from_text_prefix_when_no_name() -> None:
    """Sans clé name dans metadata, le titre doit être le préfixe du text avant ':'."""
    entry = {
        "id": "attack-pattern--abc123",
        "agent": "cyber",
        "source": "mitre-attack-v19.1",
        "text": "ARP Cache Poisoning: Adversaries may poison ARP caches to redirect traffic.",
        "metadata": {"tactic": "credential-access"},
    }
    service = WikiIngestService()
    markdown = service.ingest_entry(entry)

    assert "# ARP Cache Poisoning" in markdown, "Le titre H1 doit être le nom de la technique"
    assert 'title: "ARP Cache Poisoning"' in markdown, "Le frontmatter title doit être le nom extrait"
    assert 'title: "attack-pattern--abc123"' not in markdown, "L'UUID ne doit pas servir de titre"


def test_title_uses_name_when_present() -> None:
    """Si metadata.name existe, il est utilisé comme titre (non-régression)."""
    entry = {
        "id": "T1059",
        "agent": "@cyber",
        "source": "mitre-attack.jsonl",
        "text": "Command and Scripting Interpreter: Adversaries may abuse interpreters.",
        "metadata": {"name": "Command and Scripting Interpreter"},
    }
    service = WikiIngestService()
    markdown = service.ingest_entry(entry)

    assert 'title: "Command and Scripting Interpreter"' in markdown


def test_title_falls_back_to_id_when_no_name_no_colon() -> None:
    """Sans name et sans ':' dans le text, le titre retombe sur l'id."""
    entry = {
        "id": "attack-pattern--xyz789",
        "agent": "cyber",
        "source": "mitre-attack-v19.1",
        "text": "Description sans deux-points ni nom explicite",
        "metadata": {},
    }
    service = WikiIngestService()
    markdown = service.ingest_entry(entry)

    assert 'title: "attack-pattern--xyz789"' in markdown


def test_agent_gets_at_prefix_when_missing() -> None:
    """Un agent sans '@' doit être normalisé avec le préfixe '@' (convention SCHEMA)."""
    entry = {
        "id": "T1000",
        "agent": "cyber",
        "source": "mitre-attack.jsonl",
        "text": "Some Technique: description.",
        "metadata": {"name": "Some Technique"},
    }
    service = WikiIngestService()
    markdown = service.ingest_entry(entry)

    assert 'agent: "@cyber"' in markdown, "L'agent doit être normalisé avec @"


def test_agent_at_prefix_not_duplicated() -> None:
    """Un agent déjà préfixé par '@' ne doit pas être dupliqué en '@@'."""
    entry = {
        "id": "T1001",
        "agent": "@cyber",
        "source": "mitre-attack.jsonl",
        "text": "Another Technique: description.",
        "metadata": {"name": "Another Technique"},
    }
    service = WikiIngestService()
    markdown = service.ingest_entry(entry)

    assert 'agent: "@cyber"' in markdown
    assert "@@cyber" not in markdown, "Le préfixe @ ne doit pas être dupliqué"


def test_log_ingest_appends_to_log_md(tmp_path: Path) -> None:
    """log_ingest doit ajouter un enregistrement daté dans wiki/log.md."""
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()
    log_path = wiki_root / "log.md"
    log_path.write_text("# Log\n", encoding="utf-8")

    service = WikiIngestService(wiki_root=wiki_root)
    pages = [wiki_root / "pages" / "concepts" / "T-test.md"]

    service.log_ingest("mitre-attack.jsonl", 1, pages)

    content = log_path.read_text(encoding="utf-8")
    assert "mitre-attack.jsonl" in content, "Le dataset doit être mentionné"
    assert "T-test.md" in content, "Le fichier ingéré doit être mentionné"
    assert "Pages créées : 1" in content, "Le count doit être mentionné"
