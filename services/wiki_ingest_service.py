import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from services.chunker import chunk_text
from services.vector_embedder import Embedder
from services.vector_index import VectorIndex


class WikiIngestService:
    """Service pour ingérer des entrées JSONL dans la Knowledge Base Wiki."""

    def __init__(self, wiki_root: Path = Path("wiki")) -> None:
        self.wiki_root = wiki_root
        self.pages_dir = wiki_root / "pages" / "concepts"
        self.pages_dir.mkdir(parents=True, exist_ok=True)

    def ingest_entry(self, entry: dict[str, Any]) -> str:
        """
        Génère le markdown complet pour une entrée JSONL.

        Args:
            entry: Dictionnaire avec clés id, agent, source, text, metadata

        Returns:
            String markdown complet avec frontmatter YAML
        """
        entry_id = entry["id"]
        source = entry["source"]
        text = entry["text"]

        title = self._extract_title(entry)
        agent = self._normalize_agent(str(entry["agent"]))

        # Frontmatter YAML
        frontmatter = f"""---
id: {entry_id}
title: "{title}"
type: concept
agent: "{agent}"
tags: []
sources: ["{source}:{entry_id}"]
links_to: []
created: 2026-08-17
updated: 2026-08-17
---"""

        # Résumé (150 premiers caractères)
        summary = text[:150] + "..." if len(text) > 150 else text

        # Markdown complet
        markdown = f"""{frontmatter}

# {title}

## Résumé
{summary}

## Contenu
{text}

## Liens
(Aucun lien pour l'instant — sera enrichi en Phase 2)

## Sources
- `{source}#{entry_id}`
"""
        return markdown

    def _extract_title(self, entry: dict[str, Any]) -> str:
        """
        Extrait un titre humain de l'entrée.

        Priorité : metadata.name > préfixe du text avant ':' > id (fallback).
        """
        metadata = entry.get("metadata", {})
        name = metadata.get("name")
        if name:
            return str(name)

        text = entry.get("text", "")
        if ":" in text:
            prefix = text.split(":", 1)[0].strip()
            if prefix:
                return str(prefix)

        return str(entry["id"])

    def _normalize_agent(self, agent: str) -> str:
        """Normalise l'agent avec un préfixe '@' unique (convention SCHEMA.md).

        Gère les espaces et les '@' redondants : ``" @hardware "`` -> ``"@hardware"``.
        """
        return f"@{agent.strip().lstrip('@')}"

    def ingest_entry_to_file(self, entry: dict[str, Any]) -> Path:
        """
        Génère et écrit la page dans wiki/pages/concepts/.

        Args:
            entry: Entrée JSONL à ingérer

        Returns:
            Path du fichier créé
        """
        markdown = self.ingest_entry(entry)
        file_path = self.pages_dir / f"{entry['id']}.md"
        file_path.write_text(markdown, encoding="utf-8")
        return file_path

    def ingest_batch(self, entries: list[dict[str, Any]], max_entries: int = 3) -> list[Path]:
        """
        Traite un lot d'entrées et retourne les chemins des fichiers créés.

        Args:
            entries: Liste d'entrées JSONL
            max_entries: Nombre maximum d'entrées à traiter

        Returns:
            Liste des Paths des fichiers créés
        """
        paths = []
        for entry in entries[:max_entries]:
            path = self.ingest_entry_to_file(entry)
            paths.append(path)
        return paths

    def log_ingest(self, dataset: str, count: int, pages: list[Path]) -> None:
        """
        Trace une opération d'ingest dans wiki/log.md (append, pas overwrite).

        Args:
            dataset: Nom du dataset source (ex: "mitre-attack.jsonl")
            count: Nombre de pages ingérées
            pages: Liste des chemins des pages créées
        """
        log_path = self.wiki_root / "log.md"
        timestamp = date.today().isoformat()

        entry = f"\n## {timestamp} — Ingest {dataset}\n"
        entry += f"- Pages créées : {count}\n"
        entry += "- Fichiers :\n"
        for page in pages:
            entry += f"  - `{page.name}`\n"

        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)

    def ingest_phase2(
        self,
        inference_service: Any,
        files: list[str] | None = None,
        limit: int | None = None,
        resume: bool = False,
        progress_every: int = 50,
        vector_store: Any | None = None,
    ) -> dict[str, int]:
        """
        Ingestion Phase 2 : ad-attacks-network.jsonl + multios-commands.jsonl.

        Args:
            inference_service: Service d'inférence pour calculer les embeddings
            files: Liste optionnelle des fichiers à traiter (défaut: les deux)
            limit: Nombre maximum d'entrées à ingérer (None = toutes)
            resume: Si True, saute les entrées déjà dans le checkpoint
            progress_every: Afficher progression tous les N entrées (0 = désactivé)
            vector_store: Store vectoriel runtime (VectorService) pour indexation directe.
                         Si fourni, écrit dans le store runtime au lieu de wiki_index.bin.

        Returns:
            Dict avec stats : {ingested, chunks, edges}
        """
        if files is None:
            files = ["ad-attacks-network.jsonl", "multios-commands.jsonl"]

        # Checkpoint pour reprise
        checkpoint_path = self.wiki_root / ".phase2_checkpoint.json"
        processed_ids: set[str] = set()
        if resume and checkpoint_path.exists():
            try:
                processed_ids = set(json.loads(checkpoint_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                processed_ids = set()

        use_runtime_store = vector_store is not None

        if not use_runtime_store:
            # Mode legacy : Embedder + VectorIndex local (wiki_index.bin) - à supprimer plus tard
            embedder = Embedder(inference_service)
            vector_index = VectorIndex(
                data={"documents": [], "embedding_dim": 768},
                path="wiki_index.bin",
                lock=__import__("threading").RLock(),
            )

        total_ingested = 0
        total_chunks = 0
        total_edges = 0

        # Collecter tous les chunks pour batch runtime
        batch_documents: list[tuple[str, dict[str, Any]]] = []

        # Compter le total d'entrées pour la progression
        total_entries = 0
        for jsonl_file in files:
            file_path = self.wiki_root / "sources" / jsonl_file
            if not file_path.exists():
                continue
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        total_entries += 1

        for jsonl_file in files:
            file_path = self.wiki_root / "sources" / jsonl_file
            if not file_path.exists():
                continue

            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    entry = json.loads(line)
                    self._validate_schema(entry)

                    entry_id = entry["id"]

                    # Reprise : sauter si déjà traité
                    if resume and entry_id in processed_ids:
                        continue

                    # Limite : arrêter si atteint
                    if limit is not None and total_ingested >= limit:
                        break

                    total_ingested += 1
                    processed_ids.add(entry_id)

                    # Sauvegarder le checkpoint après chaque entrée (survit à Ctrl+C)
                    if resume:
                        checkpoint_path.write_text(json.dumps(list(processed_ids)), encoding="utf-8")

                    # Progression
                    if progress_every > 0 and total_ingested % progress_every == 0:
                        print(f"Ingested {total_ingested}/{total_entries} entries...", flush=True)

                    # Chunking : 512 tokens ≈ 2048 chars, overlap 64 tokens ≈ 256 chars
                    chunks = chunk_text(entry["text"], chunk_size=2048, overlap=256, doc_id=entry["id"])

                    if use_runtime_store:
                        # Mode runtime : collecter chunks bruts, le store embedde lui-même (pas de double-embedding)
                        for chunk in chunks:
                            metadata = {
                                **entry,
                                "agent": self._normalize_agent(str(entry["agent"])),
                                "chunk_id": f"{entry_id}:{chunk['metadata']['chunk_index']}",
                                "chunk_index": chunk["metadata"]["chunk_index"],
                                "total_chunks": chunk["metadata"]["total_chunks"],
                            }
                            batch_documents.append((chunk["text"], metadata))
                            total_chunks += 1
                    else:
                        # Mode legacy : embedder local + VectorIndex local
                        for chunk in chunks:
                            embedder.embed(chunk["text"])
                            metadata = {
                                **entry,
                                "agent": self._normalize_agent(str(entry["agent"])),
                                "chunk_id": f"{entry_id}:{chunk['metadata']['chunk_index']}",
                                "chunk_index": chunk["metadata"]["chunk_index"],
                                "total_chunks": chunk["metadata"]["total_chunks"],
                            }
                            vector_index.add_document(chunk["text"], metadata)
                            total_chunks += 1

                    # Liens croisés MITRE : chercher Txxxxxx dans le texte ET metadata
                    text_matches = re.findall(r"\bT\d{4,5}(?:\.\d+)?\b", entry["text"])
                    metadata_matches = []
                    if "metadata" in entry and isinstance(entry["metadata"], dict):
                        mitre_ids = entry["metadata"].get("mitre_technique_ids", [])
                        if isinstance(mitre_ids, list):
                            metadata_matches.extend(mitre_ids)
                    all_matches = set(text_matches + metadata_matches)
                    total_edges += len(all_matches)

                # Sortir de la boucle externe si limite atteinte
                if limit is not None and total_ingested >= limit:
                    break

        if use_runtime_store and batch_documents:
            # Écrire en batch dans le store runtime (single source of truth)
            assert vector_store is not None  # mypy: guaranteed by use_runtime_store
            vector_store.index_batch(batch_documents)
            vector_store.vectorize_pending()
        elif not use_runtime_store:
            # Mode legacy : persister l'index local
            vector_index.save()

        # Progression finale
        if progress_every > 0:
            print(f"Ingested {total_ingested}/{total_entries} entries...", flush=True)

        return {"ingested": total_ingested, "chunks": total_chunks, "edges": total_edges}

    def _validate_schema(self, entry: dict[str, Any]) -> None:
        """Valide qu'une entrée a exactement les 5 clés requises."""
        required_keys = {"id", "agent", "source", "text", "metadata"}
        actual_keys = set(entry.keys())
        if actual_keys != required_keys:
            raise ValueError(f"Schéma invalide : clés attendues {required_keys}, reçues {actual_keys}")
