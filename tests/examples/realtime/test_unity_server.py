import importlib
import json
import struct
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

EXAMPLE_DIR = Path(__file__).parents[3] / "examples" / "realtime" / "unity"


@pytest.fixture()
def server_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(EXAMPLE_DIR)
    return importlib.import_module("examples.realtime.unity.server")


@pytest.fixture(autouse=True)
def reset_manager(server_module):
    server_module.manager.session_ids.clear()
    server_module.manager.active_sessions.clear()
    server_module.manager.session_contexts.clear()
    server_module.manager.websockets.clear()
    server_module.manager.owner_websockets.clear()
    yield
    server_module.manager.session_ids.clear()
    server_module.manager.active_sessions.clear()
    server_module.manager.session_contexts.clear()
    server_module.manager.websockets.clear()
    server_module.manager.owner_websockets.clear()


def test_create_and_list_sessions(server_module) -> None:
    client = TestClient(server_module.app)
    session_id = client.post("/sessions").json()["session_id"]
    sessions = client.get("/sessions").json()["sessions"]
    assert session_id in sessions


def test_websocket_forwards_messages(monkeypatch: pytest.MonkeyPatch, server_module) -> None:
    sent: dict[str, Any] = {}

    class DummySession:
        async def send_audio(self, audio_bytes: bytes) -> None:
            sent["audio"] = audio_bytes

        async def send_message(self, text: str) -> None:
            sent["text"] = text

        def __aiter__(self) -> "DummySession":
            return self

        async def __anext__(self) -> Any:
            raise StopAsyncIteration

    class DummyContext:
        async def __aenter__(self) -> DummySession:
            return DummySession()

        async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no cleanup
            return None

    class DummyRunner:
        def __init__(self, starting_agent: Any) -> None:
            pass

        async def run(self) -> DummyContext:
            return DummyContext()

    monkeypatch.setattr(server_module, "RealtimeRunner", DummyRunner)
    monkeypatch.setattr(server_module, "get_starting_agent", lambda: None)

    client = TestClient(server_module.app)
    session_id = client.post("/sessions").json()["session_id"]
    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        websocket.send_text(json.dumps({"type": "text", "text": "hola"}))
        websocket.send_text(json.dumps({"type": "audio", "data": [0, 1]}))
    assert sent["text"] == "hola"
    assert sent["audio"] == struct.pack("2h", 0, 1)
    assert session_id not in client.get("/sessions").json()["sessions"]
