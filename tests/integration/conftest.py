"""Fixtures for tests that need a real PostgreSQL database.

The database is a genuine PostgreSQL started by Testcontainers -- there is no
in-memory stand-in and nothing about the DB layer is mocked. Importing this
module starts the container, because that has to happen before any app module
is imported: ``app.db.session`` builds its engine at import time from settings,
so the ``POSTGRES_*`` variables must already point at the container by then.

The container is started once for the whole session, since starting it is by
far the most expensive thing the suite does.

If Docker is unavailable the integration tests skip with the reason rather than
erroring; ``USE_TESTCONTAINERS=0`` runs them against a local PostgreSQL on port
5434 instead, using the ``nokia_test`` database as before.

The suite runs on a single session-scoped event loop (see
asyncio_default_fixture_loop_scope in pyproject.toml). That matters for speed:
asyncpg connections are bound to the loop that opened them, so a per-test loop
would force the engine to be disposed and every connection re-established
between tests. One loop lets the pool be reused throughout.
"""

import asyncio

from tests.support import postgres_container

# Must run before the app imports below -- this is what sets POSTGRES_*.
SKIP_REASON = postgres_container.start_postgres()

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.adapters.outbound.persistence import orm  # noqa: F401,E402  (register tables)
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database_available():
    """One clear skip message instead of a wall of connection errors."""
    if SKIP_REASON:
        pytest.skip(SKIP_REASON)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema(_database_available):
    if postgres_container.container_in_use():
        # The container starts empty, so the schema comes from the real
        # migrations. That makes every integration test a check that
        # `alembic upgrade head` still works on a clean database.
        await asyncio.to_thread(postgres_container.run_migrations)
        yield
        await engine.dispose()
        postgres_container.stop_postgres()
    else:
        # Local database: it may hold leftovers from a previous run, and it is
        # not ours to migrate, so the schema is rebuilt from the metadata.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Each test starts from empty tables."""
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest_asyncio.fixture
async def client():
    """Drives the app in-process, on the same loop as the database fixtures."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def session():
    """A database session that commits what the test wrote."""
    async with SessionLocal() as s:
        yield s
        await s.commit()
