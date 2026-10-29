"""Serve the bundled mock sites, either mounted in the main app or standalone in a thread."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from types import TracebackType

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

SITES_DIR = Path(__file__).parent / "sites"


def mount_sites(app: FastAPI) -> None:
    app.mount("/sites", StaticFiles(directory=SITES_DIR, html=True), name="sites")


def create_sites_app() -> FastAPI:
    app = FastAPI(title="glassbox mock sites")
    mount_sites(app)
    return app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class SiteServer:
    """Runs the mock sites on 127.0.0.1:<random port> for the lifetime of a `with` block."""

    def __init__(self, port: int | None = None) -> None:
        self.port = port or _free_port()
        config = uvicorn.Config(
            create_sites_app(), host="127.0.0.1", port=self.port, log_level="warning"
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> SiteServer:
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("mock site server did not start")
            time.sleep(0.02)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
