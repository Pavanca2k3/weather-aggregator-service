"""Composition root for HTTP requests.

This is the only place that names both the core and the concrete adapters --
it is where the abstract ports get bound to real implementations. Routes ask
for a WeatherService and never learn which adapters they got, which is what
makes them testable against fakes.
"""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.openmeteo.geocoder import OpenMeteoGeocoder
from app.adapters.outbound.openmeteo.weather_provider import OpenMeteoWeatherProvider
from app.adapters.outbound.persistence.repository import SqlAlchemyWeatherRepository
from app.core.config import get_settings
from app.db.session import get_db
from app.domain.service import WeatherService


@lru_cache
def _geocoder() -> OpenMeteoGeocoder:
    """Built once: it owns a requests.Session whose connection pool should be
    reused rather than rebuilt per request."""
    return OpenMeteoGeocoder(url=get_settings().openmeteo_geocoding_url)


@lru_cache
def _weather_provider() -> OpenMeteoWeatherProvider:
    """Built once, for the same reason: the SDK client holds a session."""
    return OpenMeteoWeatherProvider(url=get_settings().openmeteo_forecast_url)


async def get_weather_service(db: AsyncSession = Depends(get_db)) -> WeatherService:
    """Assemble the service for this request.

    The HTTP adapters are shared, but the repository is per-request because it
    is bound to that request's transaction.
    """
    return WeatherService(
        geocoder=_geocoder(),
        provider=_weather_provider(),
        repository=SqlAlchemyWeatherRepository(db),
    )
