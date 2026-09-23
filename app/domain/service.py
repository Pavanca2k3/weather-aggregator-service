"""Use cases.

This is the application core: the sequence of steps behind each endpoint,
written against ports only. It never sees an HTTP request, a SQL statement, or
an Open-Meteo URL -- swapping Postgres for a text file or Open-Meteo for another
provider would leave this file untouched.
"""

from collections.abc import Callable
from datetime import datetime

from app.domain.errors import CityNotFound, NoReadingsForCity
from app.domain.models import WeatherReading
from app.domain.ports import GeocoderPort, WeatherProviderPort, WeatherRepositoryPort


class WeatherService:
    """Fetches, stores and retrieves weather readings.

    The collaborators are injected rather than constructed here, so tests can
    pass in-memory fakes and the production wiring can pass real adapters
    without this class knowing the difference.
    """

    def __init__(
        self,
        geocoder: GeocoderPort,
        provider: WeatherProviderPort,
        repository: WeatherRepositoryPort,
        clock: Callable[[], datetime] = WeatherReading.utcnow,
    ) -> None:
        self._geocoder = geocoder
        self._provider = provider
        self._repository = repository
        self._clock = clock

    async def fetch_and_store(self, city: str) -> WeatherReading:
        """Resolve a city, read its current conditions, and persist them.

        The reading is stored under the geocoder's canonical spelling, not
        whatever the caller typed, so "bengaluru" and "BENGALURU" accumulate
        into one city's history rather than three.

        Every call inserts a new row, even when the conditions are identical to
        the previous fetch: Open-Meteo refreshes roughly every 15 minutes, so
        two rows sharing an `observed_at` is meaningful information, not a
        duplicate to be suppressed.
        """
        city = self._require_city_name(city)
        resolved = await self._geocoder.resolve(city)
        weather = await self._provider.current(resolved.coordinates)

        reading = WeatherReading(
            city=resolved.name,
            coordinates=resolved.coordinates,
            weather=weather,
            fetched_at=self._clock(),
        )
        return await self._repository.save(reading)

    async def readings_for_city(self, city: str) -> list[WeatherReading]:
        """Every stored reading for a city, most recent first.

        Raises NoReadingsForCity rather than returning an empty list, so a
        misspelled city is reported as a miss instead of looking like a city
        that simply has no weather.
        """
        city = self._require_city_name(city)
        readings = await self._repository.list_for_city(city)
        if not readings:
            raise NoReadingsForCity(city)
        return readings

    async def latest_for_city(self, city: str) -> WeatherReading:
        """The most recently fetched reading for a city."""
        city = self._require_city_name(city)
        reading = await self._repository.latest_for_city(city)
        if reading is None:
            raise NoReadingsForCity(city)
        return reading

    @staticmethod
    def _require_city_name(city: str) -> str:
        """Reject blank input before it reaches an adapter.

        A blank name is treated as unresolvable rather than as a validation
        error, because from the caller's point of view the outcome is the same:
        there is no such city.
        """
        cleaned = city.strip()
        if not cleaned:
            raise CityNotFound(city)
        return cleaned
