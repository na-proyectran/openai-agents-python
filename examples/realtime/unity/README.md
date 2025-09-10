# Unity NPC Realtime Demo

A FastAPI server that exposes a realtime endpoint for Unity NPCs. Clients can send audio and optional text transcripts and receive agent responses. A lightweight web interface shows transcripts and event logs without capturing audio.

## Installation

Install required dependencies:

```bash
uv add fastapi uvicorn websockets
```

## Usage

Start the server:

```bash
cd examples/realtime/unity && uv run python server.py
```

Connect your Unity client to `ws://localhost:8000/ws/<session_id>` and send JSON messages:

- `{"type": "audio", "data": [int16 samples]}`
- `{"type": "text", "text": "transcription"}`

Open the browser to `http://localhost:8000` to watch the conversation and event stream. Provide the same `session_id` used by the Unity client to view its logs.

## Customization

Edit `agent.py` to change the starting agent or replace it with your own.
