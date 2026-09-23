"""Ports: the interfaces the core needs the outside world to satisfy.

These are `Protocol`s, not base classes, so they are *structural*: an adapter
satisfies a port simply by having matching methods. Adapters never import or
subclass anything from here, which keeps every dependency arrow pointing inward
at the domain.

The methods are `async` because the driven adapters are I/O bound (Postgres via
asyncpg, Open-Meteo over HTTP). Where a library is synchronous -- the
openmeteo-requests SDK is -- it is the adapter's job to bridge that, not the
core's concern.
"""

from typing import Protocol, runtime_checkable

from app.domain.models import City, Coordinates, CurrentWeather, WeatherReading


@runtime_checkable
class GeocoderPort(Protocol):
    """Turns a human-typed city name into a location."""

    async def resolve(self, city: str) -> City:
        """Return the city with its coordinates.

        Raises:
            CityNotFound: if the name cannot be resolved.
        """
        ...


@runtime_checkable
class WeatherProviderPort(Protocol):
    """Fetches current conditions for a location."""

    async def current(self, coordinates: Coordinates) -> CurrentWeather:
        """Return the provider's current conditions for this point.

        Raises:
            WeatherProviderUnavailable: if the provider errors or returns
                a response the adapter cannot interpret.
        """
        ...


@runtime_checkable
class WeatherRepositoryPort(Protocol):
    """Stores and retrieves readings."""

    async def save(self, reading: WeatherReading) -> WeatherReading:
        """Persist a reading and return it with its assigned `id`.

        Every call inserts a new row. Repeated fetches are deliberately kept as
        separate rows, so the table is an append-only history rather than a
        per-city current value.
        """
        ...

    async def list_for_city(self, city: str) -> list[WeatherReading]:
        """All readings for a city, most recent first.

        Returns an empty list when the city has no readings; deciding that an
        empty result is a 404 belongs to the service, not to storage. Matching
        on city name is case-insensitive.
        """
        ...

    async def latest_for_city(self, city: str) -> WeatherReading | None:
        """The single most recent reading, or None if the city has none."""
        ...
