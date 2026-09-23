"""A stub standing in for Open-Meteo during provider verification.

This is what the pact files are replayed against. It is intentionally dumb: it
serves the shapes the contract promises and nothing more. If the contract and
this stub ever disagree, verification fails -- which is the signal that our
recorded expectations drifted from the shape we believe Open-Meteo returns.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FIXTURES = Path(__file__).parent / "fixtures"

KNOWN_CITIES = {
    "bengaluru": {
        "id": 1277333,
        "name": "Bengaluru",
        "latitude": 12.97194,
        "longitude": 77.59369,
        "country": "India",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
        "elevation": 920.0,
    }
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802  (stdlib naming)
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/v1/search":
            self._geocode(query)
        elif parsed.path == "/v1/forecast":
            self._forecast()
        else:
            self._send(404, b"{}", "application/json")

    def do_POST(self) -> None:  # noqa: N802
        """Provider state changes are posted here and simply acknowledged.

        The stub is stateless: the contract's states ("Bengaluru is a known
        city") are already true of its fixed data, so there is nothing to set
        up. Accepting them keeps the verifier happy without pretending to do
        work.
        """
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self._send(200, b"{}", "application/json")

    def _geocode(self, query: dict) -> None:
        name = (query.get("name") or [""])[0]
        match = KNOWN_CITIES.get(name.strip().lower())
        # an unknown name is a 200 with no `results` key, not a 404
        payload = {"results": [match]} if match else {"generationtime_ms": 0.01}
        self._send(200, json.dumps(payload).encode(), "application/json")

    def _forecast(self) -> None:
        body = (FIXTURES / "forecast_current_weather.bin").read_bytes()
        self._send(200, body, "application/octet-stream")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass  # keep test output readable


class StubProvider:
    """Runs the stub on a free port for the life of a `with` block."""

    def __init__(self) -> None:
        self._server = HTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "StubProvider":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
