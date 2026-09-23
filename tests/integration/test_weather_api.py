"""API tests for the three weather endpoints.

The database is real, but Open-Meteo is replaced with fakes via FastAPI's
dependency_overrides -- these tests must not depend on the weather outside, or
they would fail when it changes and when the network is down.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.inbound.http.dependencies import get_weather_service
from app.adapters.outbound.persistence.repository import SqlAlchemyWeatherRepository
from app.db.session import get_db
from app.domain.models import City, Coordinates, CurrentWeather
from app.domain.service import WeatherService
from app.main import app
from tests.domain.fakes import FakeGeocoder, FakeWeatherProvider

BENGALURU = City("Bengaluru", Coordinates(12.97194, 77.59369), "India", "Asia/Kolkata")
MUMBAI = City("Mumbai", Coordinates(19.07283, 72.88261), "India", "Asia/Kolkata")
T0 = datetime(2026, 9, 22, 15, 0, tzinfo=UTC)


def weather(observed_at=T0, temperature=24.1):
    return CurrentWeather(
        observed_at=observed_at,
        temperature_c=temperature,
        windspeed_kmh=10.8,
        winddirection_deg=265,
        weathercode=3,
        is_day=False,
    )


@pytest.fixture
def fake_openmeteo():
    """Swap the Open-Meteo adapters for fakes, keeping the real repository."""
    geocoder = FakeGeocoder()
    geocoder.add("bengaluru", BENGALURU)
    geocoder.add("mumbai", MUMBAI)
    provider = FakeWeatherProvider(weather())

    # the repository uses the request's own session, so writes land in the
    # transaction the endpoint commits
    async def build_service(db: AsyncSession = Depends(get_db)) -> WeatherService:
        return WeatherService(
            geocoder=geocoder,
            provider=provider,
            repository=SqlAlchemyWeatherRepository(db),
            clock=lambda: T0,
        )

    app.dependency_overrides[get_weather_service] = build_service
    yield geocoder, provider
    app.dependency_overrides.clear()


async def test_fetch_stores_and_returns_the_reading(client, fake_openmeteo):
    response = await client.post("/weather/fetch", params={"city": "bengaluru"})
    assert response.status_code == 201

    body = response.json()
    assert body["city"] == "Bengaluru"  # canonical spelling, not what was typed
    assert body["temperature_c"] == 24.1
    assert body["id"] >= 1
    assert body["observed_at"].startswith("2026-09-22T15:00")
    assert set(body) == {
        "id",
        "city",
        "latitude",
        "longitude",
        "temperature_c",
        "windspeed_kmh",
        "winddirection_deg",
        "weathercode",
        "description",
        "is_day",
        "observed_at",
        "fetched_at",
    }
    assert body["description"] == "Overcast"  # weathercode 3, per WMO 4677


async def test_fetch_unknown_city_is_404(client, fake_openmeteo):
    response = await client.post("/weather/fetch", params={"city": "Atlantis"})
    assert response.status_code == 404
    assert "Atlantis" in response.json()["detail"]


async def test_fetch_requires_a_city(client, fake_openmeteo):
    assert (await client.post("/weather/fetch")).status_code == 422
    assert (await client.post("/weather/fetch", params={"city": ""})).status_code == 422


async def test_provider_failure_is_502_not_500(client, fake_openmeteo):
    _, provider = fake_openmeteo
    provider.fail_with = "upstream timeout"
    response = await client.post("/weather/fetch", params={"city": "bengaluru"})
    assert response.status_code == 502
    assert "upstream timeout" in response.json()["detail"]


async def test_list_returns_all_readings_most_recent_first(client, fake_openmeteo):
    _, provider = fake_openmeteo
    provider.weather = weather(observed_at=T0 - timedelta(hours=1), temperature=20.0)
    await client.post("/weather/fetch", params={"city": "bengaluru"})
    provider.weather = weather(observed_at=T0, temperature=24.1)
    await client.post("/weather/fetch", params={"city": "bengaluru"})

    body = (await client.get("/weather/Bengaluru")).json()
    assert [r["temperature_c"] for r in body] == [24.1, 20.0]


async def test_list_is_case_insensitive(client, fake_openmeteo):
    await client.post("/weather/fetch", params={"city": "bengaluru"})
    assert len((await client.get("/weather/BENGALURU")).json()) == 1
    assert len((await client.get("/weather/bengaluru")).json()) == 1


async def test_list_unknown_city_is_404_not_empty_list(client, fake_openmeteo):
    response = await client.get("/weather/Atlantis")
    assert response.status_code == 404
    assert response.json()["detail"]


async def test_latest_returns_one_reading(client, fake_openmeteo):
    _, provider = fake_openmeteo
    provider.weather = weather(observed_at=T0 - timedelta(hours=2), temperature=18.0)
    await client.post("/weather/fetch", params={"city": "bengaluru"})
    provider.weather = weather(observed_at=T0, temperature=24.1)
    await client.post("/weather/fetch", params={"city": "bengaluru"})

    body = (await client.get("/weather/Bengaluru/latest")).json()
    assert isinstance(body, dict)
    assert body["temperature_c"] == 24.1


async def test_latest_unknown_city_is_404(client, fake_openmeteo):
    assert (await client.get("/weather/Atlantis/latest")).status_code == 404


async def test_cities_stay_separate(client, fake_openmeteo):
    await client.post("/weather/fetch", params={"city": "bengaluru"})
    await client.post("/weather/fetch", params={"city": "mumbai"})

    assert len((await client.get("/weather/Bengaluru")).json()) == 1
    assert (await client.get("/weather/Mumbai/latest")).json()["city"] == "Mumbai"


async def test_repeated_fetches_accumulate(client, fake_openmeteo):
    for _ in range(3):
        await client.post("/weather/fetch", params={"city": "bengaluru"})
    body = (await client.get("/weather/Bengaluru")).json()
    assert len(body) == 3
    assert len({r["id"] for r in body}) == 3
