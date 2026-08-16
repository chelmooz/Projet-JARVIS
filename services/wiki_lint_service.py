from pathlib import Path


class WikiLintService:
    """Vérifie la conformité des pages wiki au SCHEMA.md (quality gate)."""

    def __init__(self, wiki_root: Path = Path("wiki")) -> None:
        self.wiki_root = wiki_root
        self.pages_dir = wiki_root / "pages" / "concepts"

    def lint_page(self, path: Path) -> list[str]:
        """
        Vérifie la conformité d'une page au SCHEMA.md.

        Returns:
            Liste de codes de problèmes (vide si conforme).
        """
        problems: list[str] = []
        content = path.read_text(encoding="utf-8")

        if not content.startswith("---\n"):
            problems.append("frontmatter:missing_start")
            return problems

        end_idx = content.find("\n---\n", 4)
        if end_idx == -1:
            problems.append("frontmatter:missing_end")
            return problems

        frontmatter = content[4:end_idx]
        body = content[end_idx + 5 :]
        fields = self._parse_frontmatter(frontmatter)

        for key in ("id", "title", "type", "agent"):
            if key not in fields:
                problems.append(f"key:missing:{key}")

        agent = fields.get("agent", "")
        if agent and not agent.startswith("@"):
            problems.append("agent:not_normalized")

        title = fields.get("title", "")
        if "attack-pattern--" in title:
            problems.append("title:is_uuid")

        for section in ("Résumé", "Contenu"):
            if f"## {section}" not in body:
                problems.append(f"section:missing:{section}")

        return problems

    def _parse_frontmatter(self, frontmatter: str) -> dict[str, str]:
        """Parse le frontmatter YAML en dict (sans dépendance externe)."""
        fields: dict[str, str] = {}
        for line in frontmatter.split("\n"):
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            fields[key.strip()] = self._clean_value(value)
        return fields

    def _clean_value(self, value: str) -> str:
        """Retire le whitespace et les quotes entourantes d'une valeur."""
        value = value.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        return value

    def lint_all(self) -> list[tuple[str, list[str]]]:
        """
        Lint toutes les pages de wiki/pages/concepts/.

        Returns:
            Liste de (nom_fichier, problèmes) pour les pages NON conformes.
            Liste vide = toutes conformes.
        """
        issues: list[tuple[str, list[str]]] = []
        if not self.pages_dir.exists():
            return issues
        for page in sorted(self.pages_dir.glob("*.md")):
            problems = self.lint_page(page)
            if problems:
                issues.append((page.name, problems))
        return issues
