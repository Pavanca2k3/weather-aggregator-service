"""Geocoding adapter: city name -> coordinates.

Uses plain JSON rather than the openmeteo-requests SDK. That is not a
preference -- Open-Meteo's geocoding service does not speak the SDK's
protobuf/flatbuffer format and rejects the request outright, so JSON is the
only option for this endpoint.

`requests` is synchronous, so calls are pushed to a worker thread to keep the
event loop free. Bridging a blocking library is exactly the kind of detail a
driven adapter exists to hide from the core.
"""

import anyio.to_thread
import requests

from app.adapters.outbound.openmeteo.session import build_session
from app.domain.errors import CityNotFound, WeatherProviderUnavailable
from app.domain.models import City, Coordinates

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


class OpenMeteoGeocoder:
    """Implements GeocoderPort without importing it (structural typing)."""

    def __init__(
        self,
        url: str = GEOCODING_URL,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._session = session if session is not None else build_session()

    async def resolve(self, city: str) -> City:
        payload = await anyio.to_thread.run_sync(self._search, city)

        results = payload.get("results") or []
        if not results:
            raise CityNotFound(city)

        top = results[0]
        try:
            coordinates = Coordinates(
                latitude=float(top["latitude"]),
                longitude=float(top["longitude"]),
            )
            name = str(top["name"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherProviderUnavailable(f"malformed geocoding result: {exc}") from exc

        return City(
            name=name,
            coordinates=coordinates,
            country=top.get("country"),
            timezone=top.get("timezone"),
        )

    def _search(self, city: str) -> dict:
        try:
            response = self._session.get(
                self._url,
                params={"name": city, "count": 1, "language": "en", "format": "json"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise WeatherProviderUnavailable(f"geocoding request failed: {exc}") from exc
        except ValueError as exc:  # non-JSON body
            raise WeatherProviderUnavailable(f"geocoding returned non-JSON: {exc}") from exc
