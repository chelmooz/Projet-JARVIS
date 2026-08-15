from __future__ import annotations

import gzip

import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request

import controllers.static_cache as cache


def request_with_headers(headers: dict[str, str]) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    scope = {"type": "http", "method": "GET", "path": "/", "headers": raw}
    return Request(scope)


def test_cache_control_and_media_types(tmp_path) -> None:
    assert cache.cache_control_for("file.js") == "public, max-age=3600"
    assert cache.cache_control_for("file.html") == "public, max-age=60"
    assert cache.cache_control_for("file.bin") == "no-store"
    assert cache._guess_media_type("file.css") == "text/css"
    assert cache._guess_media_type("file.unknown") == "application/octet-stream"
    path = tmp_path / "file.js"
    path.write_text("content", encoding="utf-8")
    assert cache.compute_etag(str(path)).startswith('"')
    assert "ETag" in cache._cache_headers(str(path))


def test_precompress_and_encoding_selection(monkeypatch, tmp_path) -> None:
    static = tmp_path / "static"
    target = static / "assets/js/chart.umd.min.js"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"content" * 100)
    monkeypatch.setattr(cache, "_precompressed_cache", {})
    monkeypatch.setattr(cache, "_precompressed_ready", False)
    monkeypatch.setattr(cache, "PRECOMPRESS_FILES", {"assets/js/chart.umd.min.js"})
    cache._precompress_files(str(static))
    assert cache._get_precompressed("assets/js/chart.umd.min.js", "gzip") is not None
    assert (
        cache._get_precompressed("assets/js/chart.umd.min.js", "br") is None
        or cache._get_precompressed("assets/js/chart.umd.min.js", "br")[1] == "br"
    )
    assert cache._get_precompressed("missing", "gzip") is None
    assert cache._get_precompressed("assets/js/chart.umd.min.js", "identity") is None


def test_serve_cached_file_missing_etag_and_304(tmp_path) -> None:
    missing = cache.serve_cached_file(str(tmp_path / "missing.js"))
    assert missing is None
    path = tmp_path / "file.js"
    path.write_text("content", encoding="utf-8")
    response = cache.serve_cached_file(str(path))
    assert response is not None
    etag = cache.compute_etag(str(path))
    not_modified = cache.serve_cached_file(str(path), request_with_headers({"if-none-match": etag}))
    assert not_modified.status_code == 304


def test_serve_precompressed_response(monkeypatch, tmp_path) -> None:
    static = tmp_path / "static"
    path = static / "assets/js/chart.umd.min.js"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"content")
    monkeypatch.setenv("JARVIS_STATIC_DIR", str(static))
    monkeypatch.setattr(
        cache, "_precompressed_cache", {"assets/js/chart.umd.min.js": (gzip.compress(b"compressed"), None)}
    )
    response = cache.serve_cached_file(str(path), request_with_headers({"accept-encoding": "gzip"}))
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"


def test_precompress_ready_missing_file_and_brotli_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cache, "_precompressed_cache", {})
    monkeypatch.setattr(cache, "_precompressed_ready", True)
    cache._precompress_files(str(tmp_path))
    assert cache._precompressed_cache == {}
    monkeypatch.setattr(cache, "_precompressed_ready", False)
    monkeypatch.setattr(cache, "PRECOMPRESS_FILES", {"missing.js"})
    cache._precompress_files(str(tmp_path))
    assert cache._precompressed_ready is True


def test_serve_cached_file_handles_relative_path_value_error(monkeypatch, tmp_path) -> None:
    path = tmp_path / "file.js"
    path.write_text("content", encoding="utf-8")
    monkeypatch.setenv("JARVIS_STATIC_DIR", str(tmp_path / "other"))
    response = cache.serve_cached_file(str(path), request_with_headers({"accept-encoding": "gzip"}))
    assert response is not None


def test_cached_static_files_response_and_not_found(tmp_path) -> None:
    import asyncio

    static = tmp_path / "static"
    static.mkdir()
    file_path = static / "index.js"
    file_path.write_text("console.log(1)", encoding="utf-8")
    cached = cache.CachedStaticFiles(directory=str(static))
    scope = {"type": "http", "method": "GET", "path": "/index.js", "headers": []}
    response = asyncio.run(cached.get_response("index.js", scope))
    assert response.status_code == 200
    assert "cache-control" in response.headers
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(cached.get_response("missing.js", scope))
    assert exc_info.value.status_code == 404


def test_cached_static_files_etag_304(tmp_path) -> None:
    import asyncio

    static = tmp_path / "static"
    static.mkdir()
    file_path = static / "index.js"
    file_path.write_text("console.log(1)", encoding="utf-8")
    cached = cache.CachedStaticFiles(directory=str(static))
    etag = cache.compute_etag(str(file_path))
    scope = {"type": "http", "method": "GET", "path": "/index.js", "headers": [(b"if-none-match", etag.encode())]}
    response = asyncio.run(cached.get_response("index.js", scope))
    assert response.status_code == 304
