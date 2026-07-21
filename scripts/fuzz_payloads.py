"""Fuzz payload generator for API routes (P5 Ch3).

Generates valid/invalid/boundary payloads from Pydantic models.
Zero external dependencies (no Hypothesis).
"""
from typing import get_args, get_origin


def _gen_value_for_type(field_type, field_info) -> list:
    """Generate a list of test values for a given field type."""
    origin = get_origin(field_type)

    values = []

    # String types
    if field_type is str or origin is str:
        values.append("a")                    # minimal valid
        values.append("")                     # empty string
        if field_info and getattr(field_info, "min_length", None) == 1:
            pass  # empty already covered
        values.append("a" * 100)              # moderate
        values.append("a" * 10000)            # large (but not infinite)

    # Integer types
    if field_type is int:
        values.append(0)
        values.append(1)
        values.append(-1)
        values.append(999999999)

    # Float types
    if field_type is float:
        values.append(0.0)
        values.append(1.5)
        values.append(-1.0)

    # Boolean
    if field_type is bool:
        values.append(True)
        values.append(False)

    # Optional / Union types: add None
    if origin is not None:
        values.append(None)

    return values


def generate_fuzz_payloads(model_cls) -> list[dict]:
    """Generate a list of fuzz payloads for a given Pydantic model class.

    Returns at most 50 distinct payloads covering valid, boundary, and invalid cases.
    """
    from pydantic import BaseModel

    if not (isinstance(model_cls, type) and issubclass(model_cls, BaseModel)):
        return [{}]

    payloads = []
    fields = model_cls.model_fields

    # 1. Standard valid payload (all fields)
    valid = {}
    for name, info in fields.items():
        try:
            if info.is_required():
                if info.annotation is str or get_origin(info.annotation) is str:
                    valid[name] = "test"
                elif info.annotation is int:
                    valid[name] = 0
                elif info.annotation is float:
                    valid[name] = 0.0
                elif info.annotation is bool:
                    valid[name] = True
                else:
                    valid[name] = None
            else:
                valid[name] = info.default
        except Exception:
            valid[name] = None
    payloads.append(valid)

    # 2. Per-field fuzzing: for each required field, try empty/wrong type
    for name, info in fields.items():
        base = valid.copy()

        # Empty string for str fields
        if info.annotation is str or (get_origin(info.annotation) is str and type(None) in get_args(info.annotation)):
            empty = base.copy()
            empty[name] = ""
            payloads.append(empty)

        # Wrong type: int instead of str
        if info.annotation is str:
            wrong = base.copy()
            wrong[name] = 12345
            payloads.append(wrong)
        elif info.annotation is int:
            wrong = base.copy()
            wrong[name] = "not_an_int"
            payloads.append(wrong)

        # None for required fields (should trigger 422)
        if info.is_required():
            none_payload = base.copy()
            none_payload[name] = None
            payloads.append(none_payload)

    # 3. Edge: all fields missing (empty dict)
    payloads.append({})

    # Deduplicate and limit
    seen = set()
    unique = []
    for p in payloads:
        key = str(sorted(p.items()))
        if key not in seen:
            seen.add(key)
            unique.append(p)
            if len(unique) >= 50:
                break

    return unique


def get_route_payloads(app) -> list[tuple[str, str, list[dict]]]:
    """Return [(method, path, [payloads])] for all POST/PUT routes with Pydantic schemas."""
    from models.schemas import (
        AssignRequest,
        AuthorizePathRequest,
        FilePathRequest,
        FindFilesRequest,
        IngestRequest,
        JarvisRequest,
        PipelineRunRequest,
        VisionRequest,
    )

    # Map route -> schema class
    route_schema_map = {
        ("POST", "/api/agents/assign"): AssignRequest,
        ("POST", "/api/files/authorize"): AuthorizePathRequest,
        ("DELETE", "/api/files/authorize"): AuthorizePathRequest,
        ("POST", "/api/files/list"): FilePathRequest,
        ("POST", "/api/files/read"): FilePathRequest,
        ("POST", "/api/files/find"): FindFilesRequest,
        ("POST", "/api/ingest"): IngestRequest,
        ("POST", "/api/jarvis"): JarvisRequest,
        ("POST", "/api/pipelines/run"): PipelineRunRequest,
        ("POST", "/api/vision"): VisionRequest,
    }

    results = []
    for (method, path), schema_cls in route_schema_map.items():
        payloads = generate_fuzz_payloads(schema_cls)
        results.append((method, path, payloads))
    return results
