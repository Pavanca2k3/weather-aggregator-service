"""Domain models.

Plain dataclasses with no knowledge of HTTP, SQL, or any library. Everything
here would still make sense if the service were a CLI tool writing to a text
file.

All datetimes are timezone-aware UTC. Adapters are responsible for attaching
tzinfo on the way in; the domain never accepts a naive datetime.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.weather_codes import describe


@dataclass(frozen=True, slots=True)
class Coordinates:
    """A point on Earth."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude out of range: {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude out of range: {self.longitude}")


@dataclass(frozen=True, slots=True)
class City:
    """A city resolved to a location.

    `name` is the canonical spelling the geocoder returned ("Bengaluru"), not
    necessarily what the caller typed ("bengaluru", "BLR").
    """

    name: str
    coordinates: Coordinates
    country: str | None = None
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class CurrentWeather:
    """Conditions as reported by a weather provider.

    Mirrors Open-Meteo's `current_weather` block and nothing more: no forecast,
    no hourly series. It carries no identity and no city -- it is just "what the
    weather was at a point in time".
    """

    observed_at: datetime
    temperature_c: float
    windspeed_kmh: float
    winddirection_deg: int
    weathercode: int
    is_day: bool

    @property
    def description(self) -> str:
        """Human-readable form of `weathercode`, per WMO 4677."""
        return describe(self.weathercode)

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not 0 <= self.winddirection_deg <= 360:
            raise ValueError(f"winddirection out of range: {self.winddirection_deg}")
        if self.windspeed_kmh < 0:
            raise ValueError(f"windspeed cannot be negative: {self.windspeed_kmh}")


@dataclass(frozen=True, slots=True)
class WeatherReading:
    """A stored observation: the weather, plus where and when we recorded it.

    `observed_at` (inside `weather`) is when the provider measured the
    conditions; `fetched_at` is when this service asked for them. They differ
    because Open-Meteo refreshes only every ~15 minutes, so polling repeatedly
    yields new readings that share an `observed_at`.

    `id` is None until a repository has persisted it.
    """

    city: str
    coordinates: Coordinates
    weather: CurrentWeather
    fetched_at: datetime
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.city.strip():
            raise ValueError("city must not be blank")
        if self.fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(UTC)
