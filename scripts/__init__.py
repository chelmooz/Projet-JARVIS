"""Scripts opérationnels JARVIS (install, backup, release, diagnostics).

Package explicite (Lot H2) : sans ``__init__.py``, ``scripts/schedule_backup.py``
était résoluble par mypy à la fois comme module top-level ``schedule_backup``
et comme ``scripts.schedule_backup`` (namespace package), provoquant
``Source file found twice under different module names`` sur ``mypy .``.
"""

from __future__ import annotations
