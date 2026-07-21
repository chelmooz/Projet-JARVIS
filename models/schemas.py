"""Schémas Pydantic — DTO d'entrée de l'API (validation HTTP).

Chaque modèle valide un payload REST avant qu'il n'atteigne le métier.
Invariants globaux imposés par ``_StrictModel`` :

- ``extra="forbid"``  : tout champ inconnu est rejeté (422). Défensif : un
  client ne peut pas glisser de données ignorées silencieusement.
- Aucun ``str_strip_whitespace`` global : le contenu ingéré (``text``,
  ``image`` base64) doit rester intact au caractère près.

Les valeurs par défaut mutables (listes, dicts) utilisent systématiquement
``default_factory`` pour éviter le piège du mutable partagé.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Base commune — politique de validation stricte (DRY + invariant unique)
# ---------------------------------------------------------------------------

class _StrictModel(BaseModel):
    """Base de tous les DTO d'entrée : rejette les champs inconnus."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class AssignRequest(_StrictModel):
    """Réassignation d'un modèle à un profil d'agent."""

    profile: str = Field(min_length=1, description="Clé du profil d'agent")
    model: str = Field(min_length=1, description="Nom du modèle Ollama")


class JarvisRequest(_StrictModel):
    """Requête principale : envoi d'une tâche à l'orchestrateur."""

    task: str = Field(min_length=1, description="Tâche utilisateur")
    image: str | None = Field(default=None, description="Image base64 (optionnel)")
    conversation_id: str | None = Field(
        default=None, description="Conversation à poursuivre",
    )


class VisionRequest(_StrictModel):
    """Analyse d'image multimodale."""

    image: str = Field(min_length=1, description="Image encodée en base64")
    task: str = Field(default="Analyse cette image", description="Consigne d'analyse")


# ---------------------------------------------------------------------------
# Ingestion documentaire (RAG)
# ---------------------------------------------------------------------------

class IngestDocument(_StrictModel):
    """Document unitaire à indexer."""

    text: str = Field(min_length=1, description="Texte brut du document")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Métadonnées libres",
    )


class IngestRequest(_StrictModel):
    """Lot de documents à ingérer."""

    documents: list[IngestDocument] = Field(
        default_factory=list, description="Documents à indexer",
    )
    source: str = Field(default="manual", description="Origine du lot")


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

class PipelineRunRequest(_StrictModel):
    """Exécution d'un pipeline séquentiel sur une tâche."""

    pipeline_id: str = Field(min_length=1, description="Identifiant du pipeline")
    task: str = Field(min_length=1, description="Tâche d'entrée du pipeline")
    context: dict[str, Any] | None = Field(
        default=None, description="Contexte injecté aux étapes",
    )


# ---------------------------------------------------------------------------
# Accès fichiers
# ---------------------------------------------------------------------------

class AuthorizePathRequest(_StrictModel):
    """Autorisation d'accès à un dossier local."""

    path: str = Field(min_length=1, description="Chemin du dossier à autoriser")


class FilePathRequest(_StrictModel):
    """Référence à un fichier ou dossier local."""

    path: str = Field(min_length=1, description="Chemin du fichier ou dossier")


class FindFilesRequest(_StrictModel):
    """Recherche de fichiers par motif glob."""

    pattern: str = Field(
        min_length=1, description="Glob pattern (ex: C:/logs/**/*.log)",
    )


__all__ = [
    "AssignRequest",
    "JarvisRequest",
    "VisionRequest",
    "IngestDocument",
    "IngestRequest",
    "PipelineRunRequest",
    "AuthorizePathRequest",
    "FilePathRequest",
    "FindFilesRequest",
]
