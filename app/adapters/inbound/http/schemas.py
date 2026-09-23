"""HTTP response shapes.

Deliberately separate from the domain models. `WeatherReading` nests
`Coordinates` and `CurrentWeather` because that is how the concepts relate;
the JSON is flat because that is easier to consume. Keeping them apart means
the wire format can change without touching the core, and a domain refactor
cannot silently alter the public API.

The mapping is explicit rather than `from_attributes=True`, since pydantic
cannot flatten the nested domain object on its own.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.models import WeatherReading


class WeatherReadingOut(BaseModel):
    """A stored reading as returned by the API."""

    id: int = Field(..., description="Identifier of the stored reading")
    city: str = Field(..., description="Canonical city name as resolved by the geocoder")

    latitude: float
    longitude: float

    temperature_c: float = Field(..., description="Temperature in degrees Celsius")
    windspeed_kmh: float = Field(..., description="Wind speed in km/h")
    winddirection_deg: int = Field(..., description="Wind direction in degrees")
    weathercode: int = Field(..., description="WMO weather interpretation code")
    description: str = Field(..., description="Human-readable WMO 4677 description")
    is_day: bool = Field(..., description="True if the observation is during daylight")

    observed_at: datetime = Field(..., description="When the provider measured these conditions")
    fetched_at: datetime = Field(..., description="When this service retrieved and stored them")

    @classmethod
    def from_domain(cls, reading: WeatherReading) -> "WeatherReadingOut":
        if reading.id is None:  # pragma: no cover - a saved reading always has one
            raise ValueError("cannot serialise an unsaved reading")
        return cls(
            id=reading.id,
            city=reading.city,
            latitude=reading.coordinates.latitude,
            longitude=reading.coordinates.longitude,
            temperature_c=reading.weather.temperature_c,
            windspeed_kmh=reading.weather.windspeed_kmh,
            winddirection_deg=reading.weather.winddirection_deg,
            weathercode=reading.weather.weathercode,
            description=reading.weather.description,
            is_day=reading.weather.is_day,
            observed_at=reading.weather.observed_at,
            fetched_at=reading.fetched_at,
        )


class ErrorOut(BaseModel):
    """Error body shape, matching FastAPI's own convention."""

    detail: str
