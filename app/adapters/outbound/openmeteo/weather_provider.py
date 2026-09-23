"""Weather adapter: coordinates -> current conditions.

Uses the openmeteo-requests SDK, which returns flatbuffers rather than JSON.
The five values in a `current_weather` response arrive as an unordered list, so
they are matched on each variable's own enum tag rather than by position --
relying on index order would silently swap temperature and wind speed if
Open-Meteo ever reordered them.

The SDK is synchronous, so requests run in a worker thread.
"""

from datetime import UTC, datetime

import anyio.to_thread
import openmeteo_requests
from openmeteo_sdk.Variable import Variable

from app.adapters.outbound.openmeteo.session import build_session
from app.domain.errors import WeatherProviderUnavailable
from app.domain.models import Coordinates, CurrentWeather

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoWeatherProvider:
    """Implements WeatherProviderPort without importing it."""

    def __init__(
        self,
        url: str = FORECAST_URL,
        client: openmeteo_requests.Client | None = None,
    ) -> None:
        self._url = url
        self._client = client or openmeteo_requests.Client(session=build_session())

    async def current(self, coordinates: Coordinates) -> CurrentWeather:
        response = await anyio.to_thread.run_sync(self._fetch, coordinates)

        current = response.Current()
        if current is None:
            raise WeatherProviderUnavailable("response contained no current_weather block")

        values: dict[int, float] = {}
        for index in range(current.VariablesLength()):
            variable = current.Variables(index)
            values[variable.Variable()] = variable.Value()

        try:
            return CurrentWeather(
                observed_at=datetime.fromtimestamp(current.Time(), tz=UTC),
                temperature_c=values[Variable.temperature],
                windspeed_kmh=values[Variable.wind_speed],
                winddirection_deg=round(values[Variable.wind_direction]),
                weathercode=int(values[Variable.weather_code]),
                is_day=bool(values[Variable.is_day]),
            )
        except KeyError as exc:
            raise WeatherProviderUnavailable(
                f"current_weather missing expected variable: {exc}"
            ) from exc
        except (ValueError, OverflowError, OSError) as exc:
            raise WeatherProviderUnavailable(f"unusable current_weather values: {exc}") from exc

    def _fetch(self, coordinates: Coordinates):
        try:
            responses = self._client.weather_api(
                self._url,
                params={
                    "latitude": coordinates.latitude,
                    "longitude": coordinates.longitude,
                    # the only block this service consumes: no forecast, no hourly
                    "current_weather": True,
                    # the specification pins the unit; the domain stores km/h
                    "wind_speed_unit": "kmh",
                },
            )
        except Exception as exc:  # SDK raises its own error types
            raise WeatherProviderUnavailable(f"weather request failed: {exc}") from exc

        if not responses:
            raise WeatherProviderUnavailable("weather request returned no locations")
        return responses[0]
