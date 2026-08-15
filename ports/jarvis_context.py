"""Port du contexte applicatif — contrat typé pour warmup/status (audit P8).

``JarvisContext`` déclare les attributs **garantis** sur le chemin de production
(``controllers/di.py::AppContext``) :
- services de base : inference, memory, vector, conversations, log ;
- état : status_cache, _initialized, _warmup_tasks ;
- cycle de vie : initialize().

Les attributs réellement optionnels (``ingest_queue``, ``stop_event``,
``cache_lock``, ``init_report``, ``ready``) ne font PAS partie du contrat : ils
ne sont jamais posés sur ``AppContext`` (fournis uniquement par des contextes
de test) et restent lus via ``getattr`` défensif — commenté aux points d'usage.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JarvisContext(Protocol):
    """Contexte applicatif minimal consommé par warmup et status."""

    inference: Any | None
    memory: Any | None
    vector: Any | None
    conversations: Any | None
    log: Any | None
    status_cache: dict[str, Any]
    _initialized: bool
    _warmup_tasks: list[asyncio.Task[Any]]

    def initialize(self) -> None: ...
