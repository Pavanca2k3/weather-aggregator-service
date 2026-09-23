"""SQLAlchemy table for stored readings.

This is an adapter detail, deliberately separate from the domain's
WeatherReading. The domain model nests Coordinates and CurrentWeather because
that is how the concepts relate; the table flattens them because that is how
rows work. Keeping the two apart means a schema change cannot reach into the
core.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeatherReadingRow(Base):
    __tablename__ = "weather_readings"

    id: Mapped[int] = mapped_column(primary_key=True)

    city: Mapped[str] = mapped_column(String(120), nullable=False)
    # accent- and case-folded form of `city`, so a caller who fetched with an
    # ASCII name can still read back a reading stored as "Timisoara"
    city_key: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    temperature_c: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    windspeed_kmh: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    winddirection_deg: Mapped[int] = mapped_column(Integer, nullable=False)
    weathercode: Mapped[int] = mapped_column(Integer, nullable=False)
    # stored, not derived on read: the specification lists the description as
    # part of the reading, and persisting it keeps history readable even if the
    # WMO table is later corrected
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    is_day: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # when the provider measured it
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # when this service asked for it
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_weather_readings_city_key", city_key),
        Index(
            "ix_weather_readings_city_recency",
            city_key,
            observed_at.desc(),
            fetched_at.desc(),
        ),
    )
