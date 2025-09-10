from fastapi.testclient import TestClient
from pathlib import Path

from src.server import create_app
from src.organizer import MusicOrganizer


def test_startup_prefetch(tmp_path: Path, monkeypatch):
    # Arrange a source with two folders
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "albumA").mkdir(parents=True)
    (source / "albumB").mkdir(parents=True)

    org = MusicOrganizer(tmp_path / "model.gguf", source, target)

    app = create_app(org)
    with TestClient(app) as client:
        # Trigger startup
        r = client.get("/api/status")
        assert r.status_code == 200
        # A scan job should exist now
        counts = org.jobstore.counts()
        # Either still queued/analyzing or already completed depending on worker timing
        assert sum(counts.values()) >= 1

