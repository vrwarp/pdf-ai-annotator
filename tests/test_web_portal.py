"""Unit and end-to-end integration tests for the web management portal.

The portal is a FastAPI application.  These tests drive it through FastAPI's
``TestClient`` (an in-process HTTP client), exercising real request/response
cycles, template rendering, config persistence and the background processor
lifecycle.  The only thing mocked is ``process_file`` — the actual Gemini call —
so no network access or API key is needed.

The FastAPI app mounts ``static/`` and ``templates/`` using paths relative to
the current working directory, so the whole module runs from the repository
root (guaranteed by the ``_chdir_repo_root`` autouse fixture).
"""

import importlib
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _chdir_repo_root(monkeypatch):
    """Run every test from the repository root so templates/static resolve."""
    monkeypatch.chdir(REPO_ROOT)


@pytest.fixture
def portal(monkeypatch, tmp_path):
    """Import a fresh copy of the portal with a clean module-level state.

    Reloading the module resets the global processor thread, stats and log
    buffers so tests do not leak state into one another.  Input/output
    directories are pointed at throwaway temp directories.
    """
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("FILE_PATTERN", "*.pdf")

    import web_portal
    module = importlib.reload(web_portal)
    module._input_dir = input_dir  # attach for convenience in tests
    module._output_dir = output_dir
    return module


@pytest.fixture
def client(portal):
    """A TestClient bound to the freshly reloaded portal app."""
    with TestClient(portal.app) as c:
        yield c


# ── page rendering ─────────────────────────────────────────────────────────────


def test_dashboard_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Dashboard" in resp.text


def test_files_page_renders(client, portal):
    # Drop a couple of files so the listing has content to render.
    (portal._input_dir / "incoming.pdf").write_bytes(b"%PDF-1.4\n")
    (portal._output_dir / "done.pdf").write_bytes(b"%PDF-1.4\n")

    resp = client.get("/files")
    assert resp.status_code == 200
    assert "incoming.pdf" in resp.text
    assert "done.pdf" in resp.text


def test_config_page_renders(client):
    resp = client.get("/config")
    assert resp.status_code == 200
    assert "Configuration" in resp.text


def test_logs_page_renders(client):
    resp = client.get("/logs")
    assert resp.status_code == 200
    assert "Logs" in resp.text


# ── file upload / delete ────────────────────────────────────────────────────────


def test_upload_writes_file_to_input_dir(client, portal):
    resp = client.post(
        "/upload",
        files={"file": ("report.pdf", b"%PDF-1.4\n%data", "application/pdf")},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/files?msg=uploaded"
    assert (portal._input_dir / "report.pdf").exists()


def test_upload_sanitizes_path_traversal(client, portal):
    """A malicious filename is reduced to its basename before writing."""
    client.post(
        "/upload",
        files={"file": ("../../evil.pdf", b"%PDF-1.4\n", "application/pdf")},
        follow_redirects=False,
    )
    assert (portal._input_dir / "evil.pdf").exists()
    # Nothing escaped the input directory.
    assert not (portal._input_dir.parent / "evil.pdf").exists()


def test_upload_fails_without_input_dir(client, monkeypatch):
    monkeypatch.setenv("INPUT_DIR", "")
    resp = client.post(
        "/upload",
        files={"file": ("x.pdf", b"data", "application/pdf")},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_delete_removes_file(client, portal):
    target = portal._output_dir / "old.pdf"
    target.write_bytes(b"%PDF-1.4\n")

    resp = client.post("/files/delete/output/old.pdf", follow_redirects=False)
    assert resp.status_code == 303
    assert not target.exists()


def test_delete_unknown_location_rejected(client):
    resp = client.post("/files/delete/somewhere/x.pdf", follow_redirects=False)
    assert resp.status_code == 400


def test_delete_missing_file_returns_404(client):
    resp = client.post("/files/delete/input/nope.pdf", follow_redirects=False)
    assert resp.status_code == 404


# ── configuration persistence ───────────────────────────────────────────────────


def test_save_config_writes_env_file(client, monkeypatch, tmp_path):
    """POST /config persists values to a .env file in the working directory."""
    workdir = tmp_path / "cfg"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    resp = client.post(
        "/config",
        data={
            "GEMINI_KEY": "abc123",
            "INPUT_DIR": "/in",
            "OUTPUT_DIR": "/out",
            "FILE_PATTERN": "*.pdf",
            "POLL_INTERVAL": "7",
            "TASK_PAUSE_TIME": "30",
            "CAUTIOUS": "false",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    env_text = (workdir / ".env").read_text()
    assert "GEMINI_KEY" in env_text
    assert "POLL_INTERVAL" in env_text
    assert "/in" in env_text


# ── JSON API ────────────────────────────────────────────────────────────────────


def test_api_status_reports_idle(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_running"] is False
    assert body["processed"] == 0
    assert body["errors"] == 0


def test_api_logs_returns_list(client):
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    assert isinstance(resp.json()["logs"], list)


def test_processor_start_and_stop(client, portal, monkeypatch):
    """Starting the processor spawns a live thread; stopping winds it down."""
    calls = []

    def fake_process_file(path, output_dir, cautious=False):
        calls.append(path)

    # process_file is imported lazily inside the processor thread.
    monkeypatch.setattr("pdf_ai_annotator.process_file", fake_process_file)

    # Give the processor a file to pick up and a fast poll so it acts quickly.
    (portal._input_dir / "job.pdf").write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("POLL_INTERVAL", "0")
    monkeypatch.setenv("TASK_PAUSE_TIME", "0")

    start = client.post("/api/processor/start")
    assert start.status_code == 200
    assert start.json()["status"] == "started"

    # A second start while running should be a no-op.
    assert client.post("/api/processor/start").json()["status"] == "already_running"

    # Wait briefly for the background thread to process the queued file.
    deadline = time.time() + 5
    while time.time() < deadline and not calls:
        time.sleep(0.05)

    stop = client.post("/api/processor/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopping"

    assert calls, "processor thread never invoked process_file"

    status = client.get("/api/status").json()
    assert status["processed"] >= 1


def test_processor_records_errors(client, portal, monkeypatch):
    """Exceptions from process_file are counted as errors, not crashes."""
    def boom(path, output_dir, cautious=False):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("pdf_ai_annotator.process_file", boom)
    (portal._input_dir / "job.pdf").write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("POLL_INTERVAL", "0")
    monkeypatch.setenv("TASK_PAUSE_TIME", "0")

    client.post("/api/processor/start")

    deadline = time.time() + 5
    while time.time() < deadline:
        if client.get("/api/status").json()["errors"] >= 1:
            break
        time.sleep(0.05)

    client.post("/api/processor/stop")
    assert client.get("/api/status").json()["errors"] >= 1
