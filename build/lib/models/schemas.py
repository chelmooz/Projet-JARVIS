
from pydantic import BaseModel, Field


class AssignRequest(BaseModel):
    """AssignRequest."""
    profile: str = Field(min_length=1)
    model: str = Field(min_length=1)


class VisionRequest(BaseModel):
    """VisionRequest."""
    image: str = Field(min_length=1)
    task: str = "Analyse cette image"


class JarvisRequest(BaseModel):
    """JarvisRequest."""
    task: str = Field(min_length=1)
    image: str | None = None
    conversation_id: str | None = None


class IngestDocument(BaseModel):
    """IngestDocument."""
    text: str
    metadata: dict | None = {}


class IngestRequest(BaseModel):
    """IngestRequest."""
    documents: list[IngestDocument] = []
    source: str = "manual"


class PipelineRunRequest(BaseModel):
    """PipelineRunRequest."""
    pipeline_id: str = Field(min_length=1)
    task: str = Field(min_length=1)
    context: dict | None = None


class AuthorizePathRequest(BaseModel):
    """AuthorizePathRequest."""
    path: str = Field(min_length=1, description="Chemin du dossier a autoriser")


class FilePathRequest(BaseModel):
    """FilePathRequest."""
    path: str = Field(min_length=1, description="Chemin du fichier ou dossier")


class FindFilesRequest(BaseModel):
    """FindFilesRequest."""
    pattern: str = Field(min_length=1, description="Glob pattern (ex: C:/logs/**/*.log)")
