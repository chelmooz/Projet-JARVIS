"""Tests API files — Endpoints /api/files/* avec TestClient.

Cycles 5-6 : Controller + montage routes.
"""
import os
import shutil
import tempfile

from fastapi.testclient import TestClient

from controllers.router import app

client = TestClient(app)


class TestApiFilesAuth:
    """Cycle 5 — API auth endpoints."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        for p in list(client.get("/api/files/authorized").json().get("paths", [])):
            client.request("DELETE", "/api/files/authorize", json={"path": p})

    def test_authorize_ok(self):
        resp = client.post("/api/files/authorize", json={"path": self.tmpdir})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]

    def test_authorize_sans_path(self):
        resp = client.post("/api/files/authorize", json={})
        assert resp.status_code == 422  # Validation error

    def test_list_authorized(self):
        client.post("/api/files/authorize", json={"path": self.tmpdir})
        resp = client.get("/api/files/authorized")
        assert resp.status_code == 200
        assert self.tmpdir in resp.json()["paths"]

    def test_revoke_path(self):
        client.post("/api/files/authorize", json={"path": self.tmpdir})
        resp = client.request("DELETE", "/api/files/authorize", json={"path": self.tmpdir})
        assert resp.status_code == 200
        assert resp.json()["success"]

    def test_revoke_inexistant(self):
        resp = client.request("DELETE", "/api/files/authorize", json={"path": "Z:/nope"})
        assert resp.status_code == 200
        assert not resp.json()["success"]


class TestApiFilesOperations:
    """Cycle 5 — API list/read/find endpoints."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create test file
        self.test_file = os.path.join(self.tmpdir, "hello.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("Hello JARVIS!")
        # Authorize
        client.post("/api/files/authorize", json={"path": self.tmpdir})

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        for p in list(client.get("/api/files/authorized").json().get("paths", [])):
            client.request("DELETE", "/api/files/authorize", json={"path": p})

    def test_list_dir_ok(self):
        resp = client.post("/api/files/list", json={"path": self.tmpdir})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]
        names = [e["name"] for e in data["entries"]]
        assert "hello.txt" in names

    def test_list_dir_non_authorise(self):
        resp = client.post("/api/files/list", json={"path": "Z:/inexistant"})
        assert resp.status_code == 200
        assert not resp.json()["success"]

    def test_read_file_ok(self):
        resp = client.post("/api/files/read", json={"path": self.test_file})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]
        assert "Hello JARVIS!" in data["content"]

    def test_read_file_inexistant(self):
        resp = client.post("/api/files/read",
                           json={"path": os.path.join(self.tmpdir, "nope.txt")})
        assert resp.status_code == 200
        assert not resp.json()["success"]

    def test_find_files_ok(self):
        pattern = os.path.join(self.tmpdir, "**/*.txt")
        resp = client.post("/api/files/find", json={"pattern": pattern})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]
        assert len(data["matches"]) >= 1
