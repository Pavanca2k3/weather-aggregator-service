"""Component-test wiring: the real application, a stubbed Open-Meteo, a real database.

This is the same assembly the Behave suite builds in `features/environment.py`,
expressed as pytest fixtures -- deliberately the *same* shared support modules
rather than a second set of infrastructure.

Two ordering constraints shape this file:

1. `app.core.config.get_settings` is `lru_cache`d and `app.db.session` builds its
   engine at import time, so every environment variable must be in place before
   any app module is imported. The stub is therefore started at module scope,
   before `tests.support.database` (which imports the app) is imported at all.
2. `tests.support.database` builds and disposes its own engine per call, so it
   can be driven from this thread's loop while the application runs on another.
   That is why these fixtures are synchronous and never share the app's engine.
"""

import os

import pytest

from tests.support.openmeteo_stub import OpenMeteoStub

# Started first: its port is needed to build the URLs the app is configured with.
_STUB = OpenMeteoStub().start()

os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "nokia_test")
os.environ["OPENMETEO_GEOCODING_URL"] = _STUB.geocoding_url
os.environ["OPENMETEO_FORECAST_URL"] = _STUB.forecast_url
# a cached response would let one test's upstream answer leak into the next
os.environ["HTTP_CACHE_ENABLED"] = "false"

from tests.support import database  # noqa: E402  (must follow the env vars above)
from tests.support.app_server import AppServer  # noqa: E402


@pytest.fixture(scope="package")
def stub() -> OpenMeteoStub:
    """The HTTP stub standing in for Open-Meteo.

    Package-scoped, not session-scoped: the schema and the server are torn down
    as soon as the component package finishes, so this suite leaves no tables
    behind for the other suites (which build their own database) to trip over.
    """
    yield _STUB
    _STUB.stop()


@pytest.fixture(scope="package")
def app_server(stub) -> AppServer:
    """The real application, served over real HTTP against a real database."""
    database.create_schema()
    server = AppServer().start()
    yield server
    server.stop()
    database.drop_schema()


@pytest.fixture
def client(app_server):
    """An HTTP client talking to the running application."""
    with app_server.client() as http_client:
        yield http_client


@pytest.fixture(autouse=True)
def _isolated(app_server, stub):
    """Every test starts with an empty table and an unconfigured upstream."""
    stub.reset()
    database.truncate_all()
    yield


@pytest.fixture
def db() -> "Database":
    """Read-only access to what actually landed in the database."""
    return Database()


class Database:
    """Direct reads of the stored rows, for asserting persistence.

    Wraps the shared helpers and adds a row-level read. Like them, it opens and
    disposes its own engine per call, because asyncpg binds connections to the
    loop that opened them and the application is running on a different one.
    """

    @staticmethod
    def count_readings_for(city: str) -> int:
        return database.count_readings_for(city)

    @staticmethod
    def rows_for(city: str) -> list[dict]:
        """Every stored row for a city as plain dicts, most recent fetch first."""
        import asyncio

        from sqlalchemy import func, select
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.adapters.outbound.persistence.orm import WeatherReadingRow
        from app.core.config import get_settings

        async def work():
            engine = create_async_engine(get_settings().database_url)
            try:
                async with engine.connect() as conn:
                    result = await conn.execute(
                        select(WeatherReadingRow)
                        .where(func.lower(WeatherReadingRow.city) == city.strip().lower())
                        .order_by(
                            WeatherReadingRow.fetched_at.desc(),
                            WeatherReadingRow.id.desc(),
                        )
                    )
                    return [dict(row._mapping) for row in result]
            finally:
                await engine.dispose()

        return asyncio.run(work())
