"""Tests for convert_hf_sources_run.py output (schema v2 validation)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

WIKI_SOURCES = Path(__file__).parent.parent / "wiki" / "sources"

# Expected output files from conversion (local files only, parquet are best-effort)
EXPECTED_FILES = {
    "vulnerabilities.jsonl": {
        "agent": "@cyber",
        "max_lines": 1000,
        "source": "darkknight25/software_vulnerabilities_dataset",
    },
    "train.jsonl": {"agent": "@cyber", "max_lines": 2000, "source": "ethanlivertroy/nist-cybersecurity-training"},
    "LINUX_TERMINAL_COMMANDS.jsonl": {
        "agent": "@network",
        "max_lines": 600,
        "source": "darkknight25/Linux_Terminal_Commands_Dataset",
    },
    "unix-commands-dataset.jsonl": {"agent": "@network", "max_lines": None, "source": "harpomaxx/unix-commands"},
    "dataset.jsonl": {"agent": "@network", "max_lines": 2000, "source": "aelhalili/bash-commands-dataset"},
}

VALID_AGENTS = {"@cyber", "@dev", "@network", "@hardware"}


def test_output_files_exist():
    """All expected JSONL files exist in wiki/sources/."""
    for filename in EXPECTED_FILES:
        path = WIKI_SOURCES / filename
        assert path.exists(), f"Missing output file: {filename}"


@pytest.mark.parametrize("filename,expected", list(EXPECTED_FILES.items()))
def test_jsonl_schema_v2(filename: str, expected: dict):
    """Each line is valid JSON with schema v2: text, metadata.{id,agent,source}."""
    path = WIKI_SOURCES / filename
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            assert line, f"Line {i} is empty in {filename}"
            entry = json.loads(line)

            # Required keys
            assert "text" in entry, f"Line {i}: missing 'text' in {filename}"
            assert "metadata" in entry, f"Line {i}: missing 'metadata' in {filename}"

            meta = entry["metadata"]
            assert "id" in meta, f"Line {i}: missing metadata.id in {filename}"
            assert "agent" in meta, f"Line {i}: missing metadata.agent in {filename}"
            assert "source" in meta, f"Line {i}: missing metadata.source in {filename}"

            # Non-empty text
            assert entry["text"].strip(), f"Line {i}: empty text in {filename}"

            # Agent valid
            assert meta["agent"] in VALID_AGENTS, f"Line {i}: invalid agent '{meta['agent']}' in {filename}"

            # Source non-empty
            assert meta["source"].strip(), f"Line {i}: empty source in {filename}"

            # Source matches expected
            assert meta["source"] == expected["source"], f"Line {i}: source mismatch in {filename}"


@pytest.mark.parametrize("filename,expected", list(EXPECTED_FILES.items()))
def test_agent_consistency(filename: str, expected: dict):
    """All entries in a file have the same agent (per mapping table)."""
    path = WIKI_SOURCES / filename
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            assert entry["metadata"]["agent"] == expected["agent"], f"Agent mismatch in {filename}"


@pytest.mark.parametrize("filename,expected", list(EXPECTED_FILES.items()))
def test_line_count_within_cap(filename: str, expected: dict):
    """Line count does not exceed max_lines (if set)."""
    path = WIKI_SOURCES / filename
    with path.open("r", encoding="utf-8") as f:
        count = sum(1 for _ in f)
    max_lines = expected["max_lines"]
    if max_lines is not None:
        assert count <= max_lines, f"{filename}: {count} lines exceeds max {max_lines}"
    assert count > 0, f"{filename}: no entries written"


def test_no_duplicate_ids_within_file():
    """Each file has unique IDs (no duplicates within file)."""
    for filename in EXPECTED_FILES:
        path = WIKI_SOURCES / filename
        seen = set()
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                entry = json.loads(line)
                eid = entry["metadata"]["id"]
                assert eid not in seen, f"Duplicate id '{eid}' at line {i} in {filename}"
                seen.add(eid)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
