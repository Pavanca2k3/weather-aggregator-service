"""Consumer-driven contracts for the Open-Meteo adapters.

These tests state what *this service* needs from Open-Meteo, run the real
adapters against a Pact mock that serves exactly that, and write the pact files
to tests/contract/pacts/.

The value is narrow and real: if Open-Meteo renames a field or changes a type,
the contract and the adapter disagree and a test fails here, rather than the
service breaking in production.
"""

import asyncio

import pytest
from pact import match

from app.domain.errors import CityNotFound
from app.domain.models import Coordinates

# --------------------------------------------------------------------------
# Geocoding: city name -> coordinates. Plain JSON, so the contract can
# describe the shape field by field.
# --------------------------------------------------------------------------


def test_geocoding_returns_a_resolvable_city(geocoder_at, geocoding_pact):
    pact = geocoding_pact

    (
        pact.upon_receiving("a request to resolve a known city")
        .given("Bengaluru is a known city")
        .with_request("GET", "/v1/search")
        .with_query_parameter("name", "Bengaluru")
        .with_query_parameter("count", "1")
        .with_query_parameter("language", "en")
        .with_query_parameter("format", "json")
        .will_respond_with(200)
        .with_body(
            {
                "results": match.each_like(
                    {
                        # the four fields the adapter actually reads
                        "name": match.string("Bengaluru"),
                        "latitude": match.number(12.97194),
                        "longitude": match.number(77.59369),
                        "country": match.string("India"),
                        "timezone": match.string("Asia/Kolkata"),
                    }
                )
            },
            content_type="application/json",
        )
    )

    with pact.serve() as server:
        geocoder = geocoder_at(f"{server.url}/v1/search")
        city = asyncio.run(geocoder.resolve("Bengaluru"))

    assert city.name == "Bengaluru"
    assert city.coordinates == Coordinates(12.97194, 77.59369)
    assert city.country == "India"
    assert city.timezone == "Asia/Kolkata"


def test_geocoding_returns_no_results_for_an_unknown_city(geocoder_at, geocoding_pact):
    """An unresolvable name is a 200 with no `results` key, not an error status.

    Worth pinning: if Open-Meteo ever switched this to a 404, the adapter would
    raise WeatherProviderUnavailable instead of CityNotFound and the API would
    answer 502 where it should answer 404.
    """
    pact = geocoding_pact

    (
        pact.upon_receiving("a request to resolve an unknown city")
        .given("Qwertyuiopzz is not a known city")
        .with_request("GET", "/v1/search")
        .with_query_parameter("name", "Qwertyuiopzz")
        .with_query_parameter("count", "1")
        .with_query_parameter("language", "en")
        .with_query_parameter("format", "json")
        .will_respond_with(200)
        .with_body({"generationtime_ms": match.number(0.01)}, content_type="application/json")
    )

    with pact.serve() as server:
        geocoder = geocoder_at(f"{server.url}/v1/search")
        with pytest.raises(CityNotFound):
            asyncio.run(geocoder.resolve("Qwertyuiopzz"))


# --------------------------------------------------------------------------
# Forecast: coordinates -> current conditions. The SDK negotiates protobuf,
# so the contract pins recorded bytes and a content type.
# --------------------------------------------------------------------------


def test_forecast_returns_a_parsable_current_weather_block(
    weather_provider_at, recorded_forecast_body, forecast_pact
):
    pact = forecast_pact

    (
        pact.upon_receiving("a request for current weather at a coordinate")
        .given("the forecast service has current conditions for 12.97,77.59")
        .with_request("GET", "/v1/forecast")
        .with_query_parameter("latitude", "12.97194")
        .with_query_parameter("longitude", "77.59369")
        # the SDK sends Python's str(True) and asks for flatbuffers
        .with_query_parameter("current_weather", "True")
        .with_query_parameter("wind_speed_unit", "kmh")
        .with_query_parameter("format", "flatbuffers")
        .will_respond_with(200)
        .with_binary_body(recorded_forecast_body, content_type="application/octet-stream")
    )

    with pact.serve() as server:
        provider = weather_provider_at(f"{server.url}/v1/forecast")
        weather = asyncio.run(provider.current(Coordinates(12.97194, 77.59369)))

    # the five variables the service depends on, all present and typed
    assert isinstance(weather.temperature_c, float)
    assert isinstance(weather.windspeed_kmh, float)
    assert isinstance(weather.winddirection_deg, int)
    assert isinstance(weather.weathercode, int)
    assert isinstance(weather.is_day, bool)
    assert weather.observed_at.tzinfo is not None
    # the code must map to a description: it is stored, not just displayed
    assert weather.description and not weather.description.startswith("Unknown")
