"""SQLAlchemy implementation of WeatherRepositoryPort.

Translates between domain objects and table rows. The domain never sees a Row,
and the table never sees a WeatherReading -- this module is the only place that
knows both shapes.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.persistence.orm import WeatherReadingRow
from app.domain.city_key import city_key
from app.domain.models import Coordinates, CurrentWeather, WeatherReading


def to_domain(row: WeatherReadingRow) -> WeatherReading:
    return WeatherReading(
        id=row.id,
        city=row.city,
        coordinates=Coordinates(latitude=row.latitude, longitude=row.longitude),
        weather=CurrentWeather(
            observed_at=row.observed_at,
            # Numeric comes back as Decimal; the domain speaks float
            temperature_c=float(row.temperature_c),
            windspeed_kmh=float(row.windspeed_kmh),
            winddirection_deg=row.winddirection_deg,
            weathercode=row.weathercode,
            is_day=row.is_day,
        ),
        fetched_at=row.fetched_at,
    )


def to_row(reading: WeatherReading) -> WeatherReadingRow:
    return WeatherReadingRow(
        city=reading.city,
        city_key=city_key(reading.city),
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


class SqlAlchemyWeatherRepository:
    """Implements WeatherRepositoryPort without importing it."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, reading: WeatherReading) -> WeatherReading:
        """Always INSERT -- never update an existing row.

        Two fetches minutes apart legitimately produce identical weather, and
        both are kept so the table reads as a history of what was polled.
        """
        row = to_row(reading)
        self._session.add(row)
        # flush, not commit: the request-scoped session owns the transaction
        await self._session.flush()
        await self._session.refresh(row)
        return to_domain(row)

    async def list_for_city(self, city: str) -> list[WeatherReading]:
        result = await self._session.execute(self._by_city(city))
        return [to_domain(row) for row in result.scalars().all()]

    async def latest_for_city(self, city: str) -> WeatherReading | None:
        result = await self._session.execute(self._by_city(city).limit(1))
        row = result.scalars().first()
        return to_domain(row) if row is not None else None

    @staticmethod
    def _by_city(city: str):
        """Most recent first: newest observation wins, and among readings that
        share an observation time, the one fetched most recently.

        Matching is on the folded key, so "Timisoara" finds readings stored as
        "Timișoara".
        """
        return (
            select(WeatherReadingRow)
            .where(WeatherReadingRow.city_key == city_key(city))
            .order_by(
                WeatherReadingRow.observed_at.desc(),
                WeatherReadingRow.fetched_at.desc(),
                WeatherReadingRow.id.desc(),
            )
        )
