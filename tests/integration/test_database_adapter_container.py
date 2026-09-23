"""End-to-end tests for the database adapter against a containerised PostgreSQL.

``test_repository.py`` proves the adapter's query semantics. This module proves
the surrounding claims that only a real, disposable server can support:

* the rows genuinely reach PostgreSQL and survive the session that wrote them,
  so what is being tested is storage rather than an identity map;
* the schema under test is the one the migrations produce, not one conjured
  from the ORM metadata.

Nothing here is mocked or faked -- the only substitution anywhere in the stack
is that the container replaces a hand-provisioned database.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.adapters.outbound.persistence.repository import SqlAlchemyWeatherRepository
from app.db.session import SessionLocal, engine
from app.domain.models import Coordinates, CurrentWeather, WeatherReading
from tests.support import postgres_container

COORDS = Coordinates(12.97194, 77.59369)
T0 = datetime(2026, 9, 22, 15, 0, tzinfo=UTC)

pytestmark = pytest.mark.skipif(
    not postgres_container.container_in_use(),
    reason="needs the Testcontainers PostgreSQL (Docker unavailable, or USE_TESTCONTAINERS=0)",
)


def reading(city="Bengaluru", observed_at=T0, fetched_at=T0, temperature=24.1):
    return WeatherReading(
        city=city,
        coordinates=COORDS,
        weather=CurrentWeather(
            observed_at=observed_at,
            temperature_c=temperature,
            windspeed_kmh=10.8,
            winddirection_deg=265,
            weathercode=3,
            is_day=False,
        ),
        fetched_at=fetched_at,
    )


async def test_the_database_is_a_real_postgres_server():
    async with engine.connect() as conn:
        version = (await conn.execute(text("select version()"))).scalar_one()
    assert version.startswith("PostgreSQL")


async def test_the_schema_was_built_by_the_migrations():
    """The container starts empty, so these objects can only come from Alembic."""
    head_sql = text("select version_num from alembic_version")
    columns_sql = text(
        "select column_name from information_schema.columns where table_name = 'weather_readings'"
    )
    async with engine.connect() as conn:
        stamped = (await conn.execute(head_sql)).scalars().all()
        columns = set((await conn.execute(columns_sql)).scalars().all())

    # create_all would have produced the columns too, but only a migration run
    # produces them *and* an alembic_version stamp
    assert len(stamped) == 1, "database should be stamped at exactly one head revision"
    assert "description" in columns, "the newest migration's column is missing"
    assert {"city", "latitude", "longitude", "observed_at", "fetched_at"} <= columns


async def test_save_then_retrieve_by_city_and_latest_across_sessions():
    """The whole adapter contract in one pass, over three separate sessions.

    Reading back through a session that never saw the write is the point: it
    can only succeed if the row was really committed to PostgreSQL.
    """
    async with SessionLocal() as s:
        repo = SqlAlchemyWeatherRepository(s)
        older = await repo.save(reading(observed_at=T0 - timedelta(hours=1), temperature=18.0))
        newer = await repo.save(reading(observed_at=T0, temperature=24.1))
        await s.commit()

    assert older.id is not None and newer.id is not None

    async with SessionLocal() as s:
        by_city = await SqlAlchemyWeatherRepository(s).list_for_city("Bengaluru")

    assert [r.id for r in by_city] == [newer.id, older.id]  # newest observation first
    assert [r.weather.temperature_c for r in by_city] == [24.1, 18.0]
    assert by_city[0].coordinates == COORDS
    assert by_city[0].weather.observed_at == T0

    async with SessionLocal() as s:
        latest = await SqlAlchemyWeatherRepository(s).latest_for_city("Bengaluru")

    assert latest is not None
    assert latest.id == newer.id
    assert latest.weather.temperature_c == 24.1


async def test_rollback_leaves_nothing_behind():
    """A real transaction, not an in-memory list that forgets to undo itself."""
    async with SessionLocal() as s:
        await SqlAlchemyWeatherRepository(s).save(reading(city="Atlantis"))
        await s.rollback()

    async with SessionLocal() as s:
        assert await SqlAlchemyWeatherRepository(s).list_for_city("Atlantis") == []
