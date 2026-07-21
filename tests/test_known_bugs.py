from starlette.testclient import TestClient

from controllers.router import app

client = TestClient(app)


def test_files_browse_route_exists():
    """GET /api/files/browse est monté et répond (délègue à list_dir sécurisé)."""
    resp = client.get("/api/files/browse", params={"path": "."})
    assert resp.status_code == 200
    body = resp.json()
    assert "success" in body


def test_files_drives_route_exists():
    """GET /api/files/drives est monté et renvoie la liste des lecteurs."""
    resp = client.get("/api/files/drives")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert "drives" in body
    assert isinstance(body["drives"], list)
