"""Runs the real application in a background thread for end-to-end tests.

The BDD scenarios talk to it over real HTTP, so nothing about the app is
patched or substituted -- only its Open-Meteo URLs point at the stub, through
ordinary settings.
"""

import socket
import threading
import time

import httpx
import uvicorn


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class AppServer:
    def __init__(self) -> None:
        self.port = _free_port()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 30.0) -> "AppServer":
        # imported here so the caller can set environment variables first:
        # app.db.session builds its engine at import time
        from app.main import app

        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                httpx.get(f"{self.url}/health", timeout=2.0)
                return self
            except Exception:
                time.sleep(0.1)
        raise RuntimeError(f"application did not start within {timeout}s")

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=10)

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=self.url, timeout=30.0)
