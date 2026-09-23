"""In-memory stand-ins for the driven adapters.

These satisfy the ports structurally -- note that none of them imports or
subclasses GeocoderPort, WeatherProviderPort or WeatherRepositoryPort. That is
the whole point of Protocols: the dependency arrow points inward only.
"""

from dataclasses import replace

from app.domain.errors import CityNotFound, WeatherProviderUnavailable
from app.domain.models import City, Coordinates, CurrentWeather, WeatherReading


class FakeGeocoder:
    def __init__(self, known: dict[str, City] | None = None) -> None:
        self.known = known or {}
        self.calls: list[str] = []

    def add(self, lookup: str, city: City) -> None:
        self.known[lookup.casefold()] = city

    async def resolve(self, city: str) -> City:
        self.calls.append(city)
        try:
            return self.known[city.casefold()]
        except KeyError:
            raise CityNotFound(city) from None


class FakeWeatherProvider:
    def __init__(self, weather: CurrentWeather | None = None) -> None:
        self.weather = weather
        self.fail_with: str | None = None
        self.calls: list[Coordinates] = []

    async def current(self, coordinates: Coordinates) -> CurrentWeather:
        self.calls.append(coordinates)
        if self.fail_with is not None:
            raise WeatherProviderUnavailable(self.fail_with)
        assert self.weather is not None, "FakeWeatherProvider has no weather configured"
        return self.weather


class InMemoryWeatherRepository:
    """Mimics the real repository's contract: append-only, case-insensitive
    city matching, most-recent-first ordering."""

    def __init__(self) -> None:
        self.rows: list[WeatherReading] = []
        self._next_id = 1

    async def save(self, reading: WeatherReading) -> WeatherReading:
        stored = replace(reading, id=self._next_id)
        self._next_id += 1
        self.rows.append(stored)
        return stored

    async def list_for_city(self, city: str) -> list[WeatherReading]:
        matches = [r for r in self.rows if r.city.casefold() == city.casefold()]
        return sorted(matches, key=lambda r: (r.weather.observed_at, r.fetched_at), reverse=True)

    async def latest_for_city(self, city: str) -> WeatherReading | None:
        matches = await self.list_for_city(city)
        return matches[0] if matches else None
