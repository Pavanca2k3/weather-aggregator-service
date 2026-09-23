"""An HTTP-level stub standing in for Open-Meteo.

Shared by the component tests and the BDD steps -- neither builds its own.

Why a real server rather than the `responses` library: the weather adapter goes
through the openmeteo-requests SDK, which uses `niquests`, not `requests`.
`responses` patches `requests` only, so it silently fails to intercept the
weather call and the test reaches the live internet. A real socket stubs both
transports honestly, and is what the app is pointed at via
OPENMETEO_*_URL settings rather than by patching anything inside it.

Tests drive it by declaring what the upstream should say:

    stub.set_city("Bengaluru", latitude=12.97, longitude=77.59)
    stub.fail_forecast_with(503)
"""

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RECORDED_FORECAST = (
    Path(__file__).resolve().parents[1] / "contract" / "fixtures" / ("forecast_current_weather.bin")
)


@dataclass
class StubCity:
    name: str
    latitude: float
    longitude: float
    country: str = "India"
    timezone: str = "Asia/Kolkata"

    def as_result(self) -> dict:
        return {
            "id": abs(hash(self.name)) % 10_000_000,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "country": self.country,
            "timezone": self.timezone,
        }


@dataclass
class StubState:
    """Everything a test can control, plus what the stub saw."""

    cities: dict[str, StubCity] = field(default_factory=dict)
    forecast_body: bytes = b""
    geocoding_status: int = 200
    forecast_status: int = 200
    requests_seen: list[str] = field(default_factory=list)


class _Handler(BaseHTTPRequestHandler):
    state: StubState  # set on the handler class by OpenMeteoStub

    def do_GET(self) -> None:  # noqa: N802  (stdlib naming)
        parsed = urlparse(self.path)
        self.state.requests_seen.append(self.path)

        if parsed.path.endswith("/search"):
            self._geocode(parse_qs(parsed.query))
        elif parsed.path.endswith("/forecast"):
            self._forecast()
        else:
            self._send(404, b"{}", "application/json")

    def _geocode(self, query: dict) -> None:
        if self.state.geocoding_status != 200:
            self._send(self.state.geocoding_status, b"{}", "application/json")
            return

        name = (query.get("name") or [""])[0].strip().lower()
        city = self.state.cities.get(name)
        # an unknown name is a 200 with no `results` key -- see the pact
        payload = {"results": [city.as_result()]} if city else {"generationtime_ms": 0.01}
        self._send(200, json.dumps(payload).encode(), "application/json")

    def _forecast(self) -> None:
        if self.state.forecast_status != 200:
            self._send(self.state.forecast_status, b"upstream error", "text/plain")
            return
        self._send(200, self.state.forecast_body, "application/octet-stream")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


class OpenMeteoStub:
    """A stub Open-Meteo on a free port. Use as a context manager."""

    def __init__(self) -> None:
        self.state = StubState(forecast_body=RECORDED_FORECAST.read_bytes())
        handler = type("BoundHandler", (_Handler,), {"state": self.state})
        self._server = HTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # ---- what the app is configured with -------------------------------

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    @property
    def geocoding_url(self) -> str:
        return f"{self.base_url}/v1/search"

    @property
    def forecast_url(self) -> str:
        return f"{self.base_url}/v1/forecast"

    # ---- what a test declares ------------------------------------------

    def set_city(self, name: str, latitude: float, longitude: float, **kwargs) -> None:
        self.state.cities[name.strip().lower()] = StubCity(name, latitude, longitude, **kwargs)

    def forget_cities(self) -> None:
        self.state.cities.clear()

    def fail_forecast_with(self, status: int) -> None:
        self.state.forecast_status = status

    def fail_geocoding_with(self, status: int) -> None:
        self.state.geocoding_status = status

    def reset(self) -> None:
        self.state.cities.clear()
        self.state.geocoding_status = 200
        self.state.forecast_status = 200
        self.state.requests_seen.clear()

    @property
    def requests_seen(self) -> list[str]:
        return list(self.state.requests_seen)

    # ---- lifecycle -------------------------------------------------------

    def start(self) -> "OpenMeteoStub":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> "OpenMeteoStub":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
