from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from glassbox.providers import register
from glassbox.providers.scripted import S, ScriptedProvider
from glassbox.server import create_app

LOGIN = [
    S("type", "Username", args={"text": "alice", "submit": False}),
    S("type", "Password", args={"text": "sunflower-42", "submit": True}),
    S("done", args={"success": True, "answer": "ok"}),
]


def _drain(ws: Any) -> list[dict[str, Any]]:
    msgs = []
    while True:
        m = ws.receive_json()
        msgs.append(m)
        if m["type"] == "run_finished":
            return msgs


def test_live_run_streams_frames_and_steps(tmp_path: Path) -> None:
    register("test-login", lambda: ScriptedProvider(LOGIN, name="test-login"))
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/sites/login/").status_code == 200
        # The mock sites are served by this same app.
        base = str(client.base_url)
        run_id = client.post(
            "/api/runs",
            json={"goal": "log in", "start_url": "about:blank", "model": "test-login"},
        ).json()["id"]
        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            msgs = _drain(ws)
        kinds = [m["type"] for m in msgs]
        assert kinds[0] == "hello"
        assert kinds.count("step") == 3
        steps = [m["step"] for m in msgs if m["type"] == "step"]
        assert steps[0]["screenshot_url"].startswith(f"/api/runs/{run_id}/assets/")
        assert client.get(steps[0]["screenshot_url"]).headers["content-type"] == "image/jpeg"

        trace = client.get(f"/api/runs/{run_id}").json()
        assert len(trace["steps"]) == 3
        assert client.get("/api/runs").json()[0]["id"] == run_id
        assert client.get("/api/runs/nope").status_code == 404
        assert any(t["id"] == "login-basic" for t in client.get("/api/tasks").json())
        del base


def test_takeover_forwards_input(tmp_path: Path) -> None:
    import asyncio
    import threading

    gate = threading.Event()

    class Gated(ScriptedProvider):
        async def decide(self, obs, feedback):  # type: ignore[no-untyped-def]
            # The test thread holds the model "thinking" until the human has acted.
            await asyncio.to_thread(gate.wait, 10)
            return await super().decide(obs, feedback)

    script = [S("done", args={"success": True, "answer": "ok"})]
    register("test-gated", lambda: Gated(script, name="test-gated"))
    with TestClient(create_app(tmp_path)) as client:
        run_id = client.post("/api/runs", json={"goal": "wait", "model": "test-gated"}).json()["id"]
        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            ws.send_json({"type": "pause"})
            while ws.receive_json() != {"type": "status", "status": "paused"}:
                pass
            # Typing goes to the focused page through CDP while paused.
            for ch in "hi":
                ws.send_json({"type": "input", "kind": "key", "event": "keyDown", "key": ch})
                ws.send_json({"type": "input", "kind": "key", "event": "keyUp", "key": ch})
            ws.send_json({"type": "resume", "note": "typed hi"})
            gate.set()
            msgs = _drain(ws)
        step = next(m["step"] for m in msgs if m["type"] == "step")
        # The takeover happened while the model was deciding: that decision is discarded
        # and the human's note is recorded on the step instead.
        assert step["human_note"] == "typed hi"
        assert not step["result"]["ok"]
        events = client.get(f"/api/runs/{run_id}").json()["events"]
        assert [e["kind"] for e in events] == ["run_started", "takeover", "resume"]
