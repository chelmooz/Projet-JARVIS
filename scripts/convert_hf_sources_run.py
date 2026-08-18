#!/usr/bin/env python3
"""Convert data_raw/* to wiki/sources/*.jsonl (schema v2).

Schema v2: {"text": ..., "metadata": {"id": ..., "agent": ..., "source": ...}}
- source = HF dataset id
- agent = @cyber/@dev/@network/@hardware per mapping table
- deterministic sampling with random.seed(42)
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data_raw"
WIKI_SOURCES = ROOT / "wiki" / "sources"
WIKI_SOURCES.mkdir(parents=True, exist_ok=True)

# Mapping: data_raw file -> (HF source id, agent, max_entries)
CONVERSION_MAP: dict[str, tuple[str, str, int | None]] = {
    "vulnerabilities.jsonl": (
        "darkknight25/software_vulnerabilities_dataset",
        "@cyber",
        1000,
    ),
    "train.jsonl": (
        "ethanlivertroy/nist-cybersecurity-training",
        "@cyber",
        2000,
    ),
    "LINUX_TERMINAL_COMMANDS.jsonl": (
        "darkknight25/Linux_Terminal_Commands_Dataset",
        "@network",
        600,
    ),
    "unix-commands-dataset.json": (
        "harpomaxx/unix-commands",
        "@network",
        None,  # all entries
    ),
    "dataset.json": (
        "aelhalili/bash-commands-dataset",
        "@network",
        2000,
    ),
}

# Parquet downloads (optional, best-effort)
PARQUET_MAP: dict[str, tuple[str, str, int | None]] = {
    "codesearchnet-python.parquet": (
        "Nan-Do/instructional_code-search-net-python",
        "@dev",
        2000,
    ),
    "cybersecurity-dataset.parquet": (
        "AlicanKiraz0/Cybersecurity-Dataset-v1",
        "@cyber",
        2500,
    ),
}


def build_text_vulnerabilities(entry: dict[str, Any]) -> str:
    parts = [
        f"Language: {entry.get('language', '')}",
        f"Vulnerability Type: {entry.get('vulnerability_type', '')}",
        f"Description: {entry.get('description', '')}",
        f"Code Snippet: {entry.get('code_snippet', '')}",
        f"Exploitation Techniques: {entry.get('exploitation_techniques', '')}",
        f"Mitigation: {entry.get('mitigation', '')}",
    ]
    return "\n".join(p for p in parts if p.split(": ", 1)[1].strip())


def build_text_train(entry: dict[str, Any]) -> str:
    # messages format: [{"role": "...", "content": "..."}, ...]
    messages = entry.get("messages", [])
    parts = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role and content:
            parts.append(f"{role.upper()}: {content}")
    meta = entry.get("metadata", {})
    if meta.get("source"):
        parts.append(f"Source: {meta['source']}")
    return "\n\n".join(parts)


def build_text_linux_terminal(entry: dict[str, Any]) -> str:
    parts = [
        f"Command: {entry.get('command', '')}",
        f"Category: {entry.get('category', '')}",
        f"Description: {entry.get('description', '')}",
    ]
    if entry.get("example_output"):
        parts.append(f"Example Output: {entry['example_output']}")
    if entry.get("man_reference"):
        parts.append(f"Man Reference: {entry['man_reference']}")
    return "\n".join(parts)


def build_text_unix_commands(entry: dict[str, Any]) -> str:
    parts = [
        f"Input: {entry.get('input', '')}",
        f"Output: {entry.get('output', '')}",
        f"Instruction: {entry.get('instruction', '')}",
    ]
    return "\n".join(parts)


def build_text_bash_commands(entry: dict[str, Any]) -> str:
    parts = [
        f"Prompt: {entry.get('prompt', '')}",
        f"Response: {entry.get('response', '')}",
    ]
    return "\n".join(parts)


BUILDERS: dict[str, Any] = {
    "vulnerabilities.jsonl": build_text_vulnerabilities,
    "train.jsonl": build_text_train,
    "LINUX_TERMINAL_COMMANDS.jsonl": build_text_linux_terminal,
    "unix-commands-dataset.json": build_text_unix_commands,
    "dataset.json": build_text_bash_commands,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL or pretty-printed concatenated JSON objects."""
    content = path.read_text(encoding="utf-8")
    entries = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(content):
        # Skip whitespace
        while idx < len(content) and content[idx].isspace():
            idx += 1
        if idx >= len(content):
            break
        try:
            obj, idx = decoder.raw_decode(content, idx)
            entries.append(obj)
        except json.JSONDecodeError:
            # Fallback: try line-by-line for true JSONL
            break
    if not entries:
        # True JSONL fallback
        for line in content.splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return [data]


def convert_file(
    filename: str,
    hf_source: str,
    agent: str,
    max_entries: int | None,
) -> int:
    input_path = DATA_RAW / filename
    output_name = filename.replace(".jsonl", "").replace(".json", "") + ".jsonl"
    output_path = WIKI_SOURCES / output_name

    entries = load_jsonl(input_path) if filename.endswith(".jsonl") else load_json(input_path)

    print(f"  Loaded {len(entries)} entries from {filename}")

    # Deterministic sampling
    random.seed(42)
    if max_entries is not None and len(entries) > max_entries:
        entries = random.sample(entries, max_entries)
        print(f"  Sampled {max_entries} entries (seed=42)")

    builder = BUILDERS.get(filename)
    if not builder:
        raise ValueError(f"No builder for {filename}")

    written = 0
    with output_path.open("w", encoding="utf-8") as f:
        for i, entry in enumerate(entries):
            text = builder(entry)
            if not text.strip():
                continue

            # Generate ID
            entry_id = entry.get("id") or f"{output_name}-{i:04d}"

            out_entry = {
                "text": text,
                "metadata": {
                    "id": str(entry_id),
                    "agent": agent,
                    "source": hf_source,
                },
            }
            f.write(json.dumps(out_entry, ensure_ascii=False) + "\n")
            written += 1

    print(f"  Wrote {written} entries to {output_path}")
    return written


def try_download_parquet(
    filename: str,
    hf_repo: str,
    agent: str,
    max_entries: int | None,
) -> bool:
    """Try to download and convert parquet from HF Hub. Returns True if successful."""
    try:
        import pandas as pd
        from huggingface_hub import hf_hub_download
    except ImportError:
        print(f"  SKIP {filename}: huggingface_hub or pandas not available")
        return False

    try:
        print(f"  Downloading {hf_repo}...")
        local_path = hf_hub_download(
            repo_id=hf_repo,
            filename="train.parquet",  # common name, may vary
            repo_type="dataset",
            local_dir=DATA_RAW / ".cache",
        )
    except Exception as e:
        print(f"  SKIP {filename}: download failed ({e})")
        return False

    try:
        df = pd.read_parquet(local_path)
        print(f"  Loaded {len(df)} rows from parquet")

        random.seed(42)
        if max_entries is not None and len(df) > max_entries:
            df = df.sample(n=max_entries, random_state=42)
            print(f"  Sampled {max_entries} rows (seed=42)")

        output_name = filename.replace(".parquet", "") + ".jsonl"
        output_path = WIKI_SOURCES / output_name

        written = 0
        with output_path.open("w", encoding="utf-8") as f:
            for i, row in df.iterrows():
                # Try common text columns
                text = None
                for col in ["text", "content", "prompt", "instruction", "input", "code"]:
                    if col in row and pd.notna(row[col]):
                        text = str(row[col])
                        break
                if not text:
                    # Fallback: concatenate all string columns
                    text = " ".join(str(v) for v in row.values if pd.notna(v) and isinstance(v, str))

                if not text.strip():
                    continue

                entry_id = row.get("id") or row.get("task_id") or f"{output_name}-{i:04d}"

                out_entry = {
                    "text": text,
                    "metadata": {
                        "id": str(entry_id),
                        "agent": agent,
                        "source": hf_repo,
                    },
                }
                f.write(json.dumps(out_entry, ensure_ascii=False) + "\n")
                written += 1

        print(f"  Wrote {written} entries to {output_path}")
        return True

    except Exception as e:
        print(f"  SKIP {filename}: conversion failed ({e})")
        return False


def main() -> int:
    print("=== Converting data_raw -> wiki/sources (schema v2) ===")

    total_written = 0
    audit_rows = []

    # Process local JSON/JSONL files
    for filename, (hf_source, agent, max_entries) in CONVERSION_MAP.items():
        print(f"\nProcessing {filename} -> {hf_source} ({agent})...")
        written = convert_file(filename, hf_source, agent, max_entries)
        total_written += written
        audit_rows.append(
            {
                "file": filename.replace(".jsonl", "").replace(".json", "") + ".jsonl",
                "source_hf": hf_source,
                "agent": agent,
                "lines": written,
                "license": "Apache-2.0 / MIT / CC-BY-4.0 (varies by dataset)",
            }
        )

    # Try parquet downloads (best-effort)
    print("\n=== Attempting parquet downloads (best-effort) ===")
    for filename, (hf_repo, agent, max_entries) in PARQUET_MAP.items():
        print(f"\nTrying {hf_repo} ({agent})...")
        success = try_download_parquet(filename, hf_repo, agent, max_entries)
        if success:
            output_name = filename.replace(".parquet", "") + ".jsonl"
            audit_rows.append(
                {
                    "file": output_name,
                    "source_hf": hf_repo,
                    "agent": agent,
                    "lines": "DOWNLOADED",
                    "license": "Apache-2.0 / MIT (varies)",
                }
            )
        else:
            audit_rows.append(
                {
                    "file": filename.replace(".parquet", "") + ".jsonl",
                    "source_hf": hf_repo,
                    "agent": agent,
                    "lines": "SKIPPED",
                    "license": "N/A",
                }
            )

    # Update AUDIT_v2.md
    audit_path = WIKI_SOURCES / "AUDIT_v2.md"
    with audit_path.open("w", encoding="utf-8") as f:
        f.write("# AUDIT_v2 — Sources HF converties (schema v2)\n\n")
        f.write("| Fichier wiki/sources | Source HF | Agent | Lignes | Licence |\n")
        f.write("|---|---|---|---|---|\n")
        for row in audit_rows:
            f.write(f"| {row['file']} | {row['source_hf']} | {row['agent']} | {row['lines']} | {row['license']} |\n")
        f.write(f"\nTotal entrées converties (locales) : {total_written}\n")

    print(f"\n=== Done: {total_written} entries written ===")
    print(f"AUDIT updated: {audit_path}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
