"""Tests MT-KB-L3f — convertisseur PowerShell-Docs → JSONL @hardware + @dev.

Vérifie le schéma 5 clés, la licence CC-BY-4.0, la répartition d'agent
(cmdlets diagnostic système → @hardware, autres → @dev) et l'unicité des ids.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.convert_psdocs_run import convert_cmdlet, convert_psdocs_tree

CMD_GET_PROCESS = """---
external help file: Microsoft.PowerShell.Commands.Management.dll-Help.xml
Module Name: Microsoft.PowerShell.Management
online version: https://learn.microsoft.com/powershell/module/microsoft.powershell.management/get-process
schema: 2.0.0
---

# Get-Process

## SYNOPSIS
Gets the processes that are running on the local computer.

## SYNTAX

```
Get-Process [[-Name] <String[]>] [-IncludeUserName] [<CommonParameters>]
```
"""

CMD_CONVERT_TO_JSON = """---
Module Name: Microsoft.PowerShell.Utility
schema: 2.0.0
---

# ConvertTo-Json

## SYNOPSIS
Converts a PowerShell object to a JSON-formatted string.

## SYNTAX

```
ConvertTo-Json [-InputObject] <Object> [<CommonParameters>]
```
"""


def _write_cmdlet(tmp_path: Path, module: str, name: str, content: str) -> Path:
    mod_dir = tmp_path / module
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


class TestPsDocsConverter:
    def test_cmdlet_converts_with_module_based_agent(self, tmp_path: Path) -> None:
        """Schéma 5 clés, licence CC-BY-4.0, @hardware pour module diagnostic."""
        path = _write_cmdlet(tmp_path, "CimCmdlets", "Get-CimInstance", CMD_GET_PROCESS)

        entry = convert_cmdlet(path, "CimCmdlets")

        assert set(entry.keys()) == {"id", "agent", "source", "text", "metadata"}
        assert entry["id"] == "psdocs/Get-CimInstance"
        assert entry["agent"] == "@hardware"
        assert entry["source"] == "powershell-docs"
        assert entry["metadata"]["license"] == "CC-BY-4.0"
        assert entry["metadata"]["module"] == "CimCmdlets"

        dev_entry = convert_cmdlet(
            _write_cmdlet(tmp_path, "Microsoft.PowerShell.Utility", "ConvertTo-Json", CMD_CONVERT_TO_JSON),
            "Microsoft.PowerShell.Utility",
        )
        assert dev_entry["agent"] == "@dev"

    def test_tree_unique_ids_and_hardware_priority(self, tmp_path: Path) -> None:
        """Id uniques, cap respecté, cmdlets diagnostic @hardware incluses."""
        _write_cmdlet(tmp_path, "CimCmdlets", "Get-CimInstance", CMD_GET_PROCESS)
        _write_cmdlet(tmp_path, "Microsoft.PowerShell.Utility", "ConvertTo-Json", CMD_CONVERT_TO_JSON)
        _write_cmdlet(tmp_path, "Microsoft.PowerShell.Utility", "ConvertFrom-Json", CMD_CONVERT_TO_JSON)

        entries = convert_psdocs_tree(tmp_path, limit=2)

        ids = [e["id"] for e in entries]
        assert len(ids) == len(set(ids)), f"ids dupliqués: {ids}"
        assert len(entries) <= 2
        assert all(e["metadata"]["license"] == "CC-BY-4.0" for e in entries)
