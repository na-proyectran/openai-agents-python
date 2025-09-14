import asyncio
import base64
import json
import logging
import struct
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agents.realtime import (
    RealtimeRunner,
    RealtimeSession,
    RealtimeSessionEvent,
)

# Import class - handle both module and package use cases
if TYPE_CHECKING:
    # For type checking, use the relative import
    from .agent import get_starting_agent
else:
    # At runtime, try both import styles
    try:
        # Try relative import first (when used as a package)
        from .agent import get_starting_agent
    except ImportError:
        # Fall back to direct import (when run as a script)
        from agent import get_starting_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealtimeWebSocketManager:
    """Manage realtime sessions and attached websockets."""

    def __init__(self) -> None:
        self.active_sessions: dict[str, RealtimeSession] = {}
        self.session_contexts: dict[str, Any] = {}
        self.websockets: dict[str, set[WebSocket]] = {}
        self.owner_websockets: dict[str, WebSocket] = {}
        self.session_ids: set[str] = set()

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex
        self.session_ids.add(session_id)
        self.websockets.setdefault(session_id, set())
        return session_id

    def list_sessions(self) -> list[str]:
        return sorted(self.session_ids)

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self.websockets.setdefault(session_id, set()).add(websocket)
        if session_id not in self.session_ids:
            self.session_ids.add(session_id)

        if session_id not in self.owner_websockets:
            self.owner_websockets[session_id] = websocket
            runner = RealtimeRunner(starting_agent=get_starting_agent())
            session_context = await runner.run()
            session = await session_context.__aenter__()
            self.active_sessions[session_id] = session
            self.session_contexts[session_id] = session_context
            asyncio.create_task(self._process_events(session_id))

    async def disconnect_websocket(self, session_id: str, websocket: WebSocket) -> None:
        websockets = self.websockets.get(session_id)
        if websockets is not None:
            websockets.discard(websocket)
        if self.owner_websockets.get(session_id) == websocket:
            await self.disconnect(session_id)

    async def disconnect(self, session_id: str) -> None:
        for ws in list(self.websockets.get(session_id, set())):
            try:
                await ws.close()
            except Exception:  # pragma: no cover - best effort
                pass
        if session_id in self.session_contexts:
            await self.session_contexts[session_id].__aexit__(None, None, None)
            del self.session_contexts[session_id]
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        self.websockets.pop(session_id, None)
        self.owner_websockets.pop(session_id, None)
        self.session_ids.discard(session_id)

    async def send_audio(self, session_id: str, audio_bytes: bytes) -> None:
        session = self.active_sessions.get(session_id)
        if session is not None:
            await session.send_audio(audio_bytes)

    async def send_text(self, session_id: str, text: str) -> None:
        session = self.active_sessions.get(session_id)
        if session is not None:
            await session.send_message(text)

    async def _process_events(self, session_id: str) -> None:
        try:
            session = self.active_sessions[session_id]
            async for event in session:
                event_data = await self._serialize_event(event)
                for ws in list(self.websockets.get(session_id, [])):
                    try:
                        await ws.send_text(json.dumps(event_data))
                    except Exception as exc:  # pragma: no cover - best effort
                        logger.error("Error sending event: %s", exc)
        except Exception as exc:  # pragma: no cover - best effort
            logger.error("Error processing events for session %s: %s", session_id, exc)

    async def _serialize_event(self, event: RealtimeSessionEvent) -> dict[str, Any]:
        base_event: dict[str, Any] = {"type": event.type}

        if event.type == "agent_start":
            base_event["agent"] = event.agent.name
        elif event.type == "agent_end":
            base_event["agent"] = event.agent.name
        elif event.type == "handoff":
            base_event["from"] = event.from_agent.name
            base_event["to"] = event.to_agent.name
        elif event.type == "tool_start":
            base_event["tool"] = event.tool.name
        elif event.type == "tool_end":
            base_event["tool"] = event.tool.name
            base_event["output"] = str(event.output)
        elif event.type == "audio":
            base_event["audio"] = base64.b64encode(event.audio.data).decode("utf-8")
        elif event.type == "history_updated":
            base_event["history"] = [item.model_dump(mode="json") for item in event.history]
        elif event.type == "guardrail_tripped":
            base_event["guardrail_results"] = [
                {"name": result.guardrail.name} for result in event.guardrail_results
            ]
        elif event.type == "raw_model_event":
            base_event["raw_model_event"] = {"type": event.data.type}
        elif event.type == "error":
            base_event["error"] = str(getattr(event, "error", "Unknown error"))
        return base_event


manager = RealtimeWebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # pragma: no cover - simple setup
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message["type"] == "audio":
                int16_data = message["data"]
                audio_bytes = struct.pack(f"{len(int16_data)}h", *int16_data)
                await manager.send_audio(session_id, audio_bytes)
            elif message["type"] == "text":
                await manager.send_text(session_id, message["text"])
    except WebSocketDisconnect:
        await manager.disconnect_websocket(session_id, websocket)


@app.post("/sessions")
async def create_session() -> dict[str, str]:
    session_id = manager.create_session()
    return {"session_id": session_id}


@app.get("/sessions")
async def list_sessions() -> dict[str, list[str]]:
    return {"sessions": manager.list_sessions()}


app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
async def read_index() -> FileResponse:
    return FileResponse("static/index.html")


if __name__ == "__main__":  # pragma: no cover - manual launch
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
