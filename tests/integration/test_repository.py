"""Repository tests against a real PostgreSQL database.

The in-memory fake used by the domain tests can only prove the service's logic.
Whether `lower(city)` matching, DESC ordering and Decimal-to-float conversion
actually behave is a property of Postgres and SQLAlchemy, so it has to be
checked against the real thing.
"""

from datetime import UTC, datetime, timedelta

import pytest_asyncio

from app.adapters.outbound.persistence.repository import SqlAlchemyWeatherRepository
from app.domain.models import Coordinates, CurrentWeather, WeatherReading

COORDS = Coordinates(12.97194, 77.59369)
T0 = datetime(2026, 9, 22, 15, 0, tzinfo=UTC)


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


@pytest_asyncio.fixture
async def repo(session):
    return SqlAlchemyWeatherRepository(session)


async def test_save_assigns_an_id_and_round_trips_values(repo):
    saved = await repo.save(reading())
    assert saved.id is not None
    assert saved.city == "Bengaluru"
    assert saved.weather.temperature_c == 24.1
    assert isinstance(saved.weather.temperature_c, float)  # not Decimal
    assert saved.weather.is_day is False
    assert saved.coordinates == COORDS


async def test_timestamps_survive_as_utc(repo):
    saved = await repo.save(reading())
    assert saved.weather.observed_at == T0
    assert saved.fetched_at == T0
    assert saved.weather.observed_at.tzinfo is not None


async def test_repeated_saves_insert_separate_rows(repo):
    await repo.save(reading())
    await repo.save(reading())  # identical weather
    rows = await repo.list_for_city("Bengaluru")
    assert len(rows) == 2
    assert rows[0].id != rows[1].id


async def test_city_matching_is_case_insensitive(repo):
    await repo.save(reading(city="Bengaluru"))
    for lookup in ("bengaluru", "BENGALURU", "  BeNgAlUrU  "):
        assert len(await repo.list_for_city(lookup)) == 1


async def test_readings_come_back_most_recent_first(repo):
    await repo.save(reading(observed_at=T0 - timedelta(hours=2), temperature=18.0))
    await repo.save(reading(observed_at=T0, temperature=24.1))
    await repo.save(reading(observed_at=T0 - timedelta(hours=1), temperature=20.0))
    rows = await repo.list_for_city("Bengaluru")
    assert [r.weather.temperature_c for r in rows] == [24.1, 20.0, 18.0]


async def test_same_observation_breaks_the_tie_on_fetched_at(repo):
    """Two polls of an unchanged reading: the later fetch sorts first."""
    await repo.save(reading(observed_at=T0, fetched_at=T0))
    await repo.save(reading(observed_at=T0, fetched_at=T0 + timedelta(minutes=5)))
    rows = await repo.list_for_city("Bengaluru")
    assert rows[0].fetched_at > rows[1].fetched_at
    assert rows[0].weather.observed_at == rows[1].weather.observed_at


async def test_latest_returns_the_newest_only(repo):
    await repo.save(reading(observed_at=T0 - timedelta(hours=1), temperature=20.0))
    await repo.save(reading(observed_at=T0, temperature=24.1))
    latest = await repo.latest_for_city("bengaluru")
    assert latest.weather.temperature_c == 24.1


async def test_unknown_city_returns_empty_and_none(repo):
    # storage reports absence plainly; turning it into a 404 is the service's job
    assert await repo.list_for_city("Atlantis") == []
    assert await repo.latest_for_city("Atlantis") is None


async def test_cities_do_not_leak_into_each_other(repo):
    await repo.save(reading(city="Bengaluru"))
    await repo.save(reading(city="Mumbai"))
    rows = await repo.list_for_city("Bengaluru")
    assert len(rows) == 1
    assert rows[0].city == "Bengaluru"


async def test_a_city_stored_with_diacritics_is_found_without_them(repo):
    """Open-Meteo answers "Timisoara" with "Timișoara".

    Storing the canonical spelling while matching on `lower(city)` meant a
    caller could fetch a city and then get a 404 reading it back.
    """
    await repo.save(reading(city="Timișoara"))

    for lookup in ("Timisoara", "timisoara", "TIMIȘOARA", "  timișoara  "):
        rows = await repo.list_for_city(lookup)
        assert len(rows) == 1, f"{lookup!r} did not find the stored reading"
        assert rows[0].city == "Timișoara"  # display name keeps its diacritics

    assert await repo.latest_for_city("Timisoara") is not None
