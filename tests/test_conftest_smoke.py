import os
from pathlib import Path


def test_sandbox_root_fixture(sandbox_root: Path) -> None:
    assert isinstance(sandbox_root, Path)
    assert sandbox_root.exists()
    assert os.environ["JARVIS_FILES_SANDBOX_ROOT"] == str(sandbox_root)
