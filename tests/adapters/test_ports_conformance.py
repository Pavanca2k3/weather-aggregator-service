"""Do the real adapters actually satisfy the ports?

Protocols are structural, so nothing forces an adapter to conform -- a renamed
or mistyped method would simply fail at runtime, deep inside a request. These
checks catch that at test time instead.

No database or network is touched: only the shapes are inspected.
"""

import inspect

from app.adapters.outbound.openmeteo.geocoder import OpenMeteoGeocoder
from app.adapters.outbound.openmeteo.weather_provider import OpenMeteoWeatherProvider
from app.adapters.outbound.persistence.repository import SqlAlchemyWeatherRepository
from app.domain.ports import GeocoderPort, WeatherProviderPort, WeatherRepositoryPort


def test_geocoder_satisfies_its_port():
    assert isinstance(OpenMeteoGeocoder(), GeocoderPort)


def test_weather_provider_satisfies_its_port():
    assert isinstance(OpenMeteoWeatherProvider(), WeatherProviderPort)


def test_repository_satisfies_its_port():
    assert isinstance(SqlAlchemyWeatherRepository(session=None), WeatherRepositoryPort)


def test_port_methods_are_coroutines():
    """The ports are async; a sync adapter method would return a coroutine-less
    value and break callers that await it."""
    pairs = [
        (OpenMeteoGeocoder, ["resolve"]),
        (OpenMeteoWeatherProvider, ["current"]),
        (SqlAlchemyWeatherRepository, ["save", "list_for_city", "latest_for_city"]),
    ]
    for adapter, methods in pairs:
        for name in methods:
            assert inspect.iscoroutinefunction(getattr(adapter, name)), (
                f"{adapter.__name__}.{name} must be async"
            )


def test_adapters_do_not_import_the_ports():
    """Structural typing means adapters need no reference to the domain's
    interfaces; keeping it that way is what points every arrow inward."""
    import app.adapters.outbound.openmeteo.geocoder as geo
    import app.adapters.outbound.openmeteo.weather_provider as wp
    import app.adapters.outbound.persistence.repository as repo

    for module in (geo, wp, repo):
        source = inspect.getsource(module)
        assert "domain.ports" not in source, f"{module.__name__} imports the ports directly"
