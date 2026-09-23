"""Contract-test fixtures.

Contract tests must never reach the real Open-Meteo, and must never read a
cached response: the whole point is to exercise our adapters against a mock
whose responses the contract itself defines. So the adapters here are always
built with a plain, uncached session.
"""

from pathlib import Path

import openmeteo_requests
import pytest
import requests
from pact import Pact

from app.adapters.outbound.openmeteo.geocoder import OpenMeteoGeocoder
from app.adapters.outbound.openmeteo.weather_provider import OpenMeteoWeatherProvider

PACT_DIR = Path(__file__).parent / "pacts"
FIXTURES = Path(__file__).parent / "fixtures"

CONSUMER = "weather-aggregator"
GEOCODING_PROVIDER = "open-meteo-geocoding"
FORECAST_PROVIDER = "open-meteo-forecast"


@pytest.fixture(scope="session")
def _reset_pact_file():
    """Truncate each provider's pact once, the first time it is written.

    Interactions are merged into the file (overwrite=False), so without a reset
    an interaction that was later renamed or deleted would linger in the
    contract forever. Resetting lazily -- rather than clearing the directory up
    front -- means running the provider tests on their own still finds the
    pacts from a previous run instead of wiping them and failing.
    """
    already_reset: set[str] = set()

    def reset(provider: str) -> None:
        if provider in already_reset:
            return
        already_reset.add(provider)
        PACT_DIR.mkdir(parents=True, exist_ok=True)
        stale = PACT_DIR / f"{CONSUMER}-{provider}.json"
        stale.unlink(missing_ok=True)

    return reset


@pytest.fixture
def geocoding_pact(_reset_pact_file):
    """A fresh Pact per test, merged into the provider's file on the way out.

    One shared Pact object cannot be reused: once it has served a mock server,
    adding another interaction to it fails.
    """
    _reset_pact_file(GEOCODING_PROVIDER)
    pact = Pact(CONSUMER, GEOCODING_PROVIDER).with_specification("V4")
    yield pact
    pact.write_file(PACT_DIR)


@pytest.fixture
def forecast_pact(_reset_pact_file):
    _reset_pact_file(FORECAST_PROVIDER)
    pact = Pact(CONSUMER, FORECAST_PROVIDER).with_specification("V4")
    yield pact
    pact.write_file(PACT_DIR)


@pytest.fixture
def uncached_session():
    return requests.Session()


@pytest.fixture
def geocoder_at(uncached_session):
    """Build the real geocoder pointed at a given base URL."""

    def build(url: str) -> OpenMeteoGeocoder:
        return OpenMeteoGeocoder(url=url, session=uncached_session)

    return build


@pytest.fixture
def weather_provider_at(uncached_session):
    """Build the real weather provider pointed at a given base URL."""

    def build(url: str) -> OpenMeteoWeatherProvider:
        client = openmeteo_requests.Client(session=uncached_session)
        return OpenMeteoWeatherProvider(url=url, client=client)

    return build


@pytest.fixture(scope="session")
def recorded_forecast_body() -> bytes:
    """A real flatbuffers response, recorded once from Open-Meteo.

    The forecast API speaks protobuf, not JSON, so the contract pins the exact
    bytes rather than a JSON shape. Our real adapter still does the parsing,
    which is what the contract is there to protect.
    """
    return (FIXTURES / "forecast_current_weather.bin").read_bytes()
