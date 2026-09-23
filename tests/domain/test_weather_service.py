"""Use-case tests.

No database, no network, no FastAPI. Every collaborator is a fake, so these run
in milliseconds and fail only when the business rules actually break.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.errors import CityNotFound, NoReadingsForCity, WeatherProviderUnavailable
from app.domain.models import City, Coordinates, CurrentWeather
from app.domain.service import WeatherService
from tests.domain.fakes import FakeGeocoder, FakeWeatherProvider, InMemoryWeatherRepository

BENGALURU = City(
    name="Bengaluru",
    coordinates=Coordinates(12.97194, 77.59369),
    country="India",
    timezone="Asia/Kolkata",
)
T0 = datetime(2026, 9, 22, 14, 30, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


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
def ctx():
    geocoder = FakeGeocoder()
    geocoder.add("bengaluru", BENGALURU)
    provider = FakeWeatherProvider(weather())
    repo = InMemoryWeatherRepository()

    def clock():
        return T0

    return geocoder, provider, repo, WeatherService(geocoder, provider, repo, clock=clock)


def test_fetch_stores_a_reading(ctx):
    _, _, repo, service = ctx
    saved = run(service.fetch_and_store("Bengaluru"))

    assert saved.id == 1
    assert saved.weather.temperature_c == 24.1
    assert saved.fetched_at == T0
    assert len(repo.rows) == 1


def test_reading_is_stored_under_the_canonical_city_name(ctx):
    _, _, repo, service = ctx
    run(service.fetch_and_store("bengaluru"))
    # caller typed lowercase; geocoder's spelling is what persists
    assert repo.rows[0].city == "Bengaluru"


def test_provider_is_called_with_the_resolved_coordinates(ctx):
    _, provider, _, service = ctx
    run(service.fetch_and_store("Bengaluru"))
    assert provider.calls == [BENGALURU.coordinates]


def test_repeated_fetches_append_rather_than_replace(ctx):
    _, _, repo, service = ctx
    run(service.fetch_and_store("Bengaluru"))
    run(service.fetch_and_store("Bengaluru"))

    # identical weather, but two rows: polling history is preserved
    assert len(repo.rows) == 2
    assert [r.id for r in repo.rows] == [1, 2]
    assert repo.rows[0].weather.observed_at == repo.rows[1].weather.observed_at


def test_unknown_city_is_rejected(ctx):
    _, provider, repo, service = ctx
    with pytest.raises(CityNotFound):
        run(service.fetch_and_store("Atlantis"))

    # nothing downstream should have been touched
    assert provider.calls == []
    assert repo.rows == []


def test_blank_city_is_rejected_without_calling_the_geocoder(ctx):
    geocoder, _, _, service = ctx
    with pytest.raises(CityNotFound):
        run(service.fetch_and_store("   "))
    assert geocoder.calls == []


def test_provider_failure_stores_nothing(ctx):
    _, provider, repo, service = ctx
    provider.fail_with = "upstream 503"
    with pytest.raises(WeatherProviderUnavailable):
        run(service.fetch_and_store("Bengaluru"))
    assert repo.rows == []


def test_readings_are_returned_most_recent_first(ctx):
    _, provider, _, service = ctx
    provider.weather = weather(observed_at=T0 - timedelta(hours=1), temperature=20.0)
    run(service.fetch_and_store("Bengaluru"))
    provider.weather = weather(observed_at=T0, temperature=24.1)
    run(service.fetch_and_store("Bengaluru"))

    readings = run(service.readings_for_city("Bengaluru"))
    assert [r.weather.temperature_c for r in readings] == [24.1, 20.0]


def test_lookup_is_case_insensitive(ctx):
    _, _, _, service = ctx
    run(service.fetch_and_store("bengaluru"))
    assert len(run(service.readings_for_city("BENGALURU"))) == 1
    assert run(service.latest_for_city("bEnGaLuRu")).city == "Bengaluru"


def test_latest_returns_the_newest_reading(ctx):
    _, provider, _, service = ctx
    provider.weather = weather(observed_at=T0 - timedelta(hours=2), temperature=18.0)
    run(service.fetch_and_store("Bengaluru"))
    provider.weather = weather(observed_at=T0, temperature=24.1)
    run(service.fetch_and_store("Bengaluru"))

    assert run(service.latest_for_city("Bengaluru")).weather.temperature_c == 24.1


def test_missing_city_raises_rather_than_returning_empty(ctx):
    _, _, _, service = ctx
    # the decision: absent data is a 404, not a silent empty success
    with pytest.raises(NoReadingsForCity):
        run(service.readings_for_city("Bengaluru"))
    with pytest.raises(NoReadingsForCity):
        run(service.latest_for_city("Bengaluru"))
