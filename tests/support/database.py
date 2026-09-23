"""Database setup shared by the component tests and the BDD steps.

Each helper builds its own short-lived engine and disposes it before
returning. That looks wasteful but is deliberate: asyncpg binds connections to
the event loop that opened them, and these helpers are called from a different
loop than the running application's. A shared engine across both would hand a
connection to the wrong loop.
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.adapters.outbound.persistence import orm  # noqa: F401  (registers tables)
from app.core.config import get_settings
from app.db.base import Base


def _run(coro_factory):
    async def runner():
        engine = create_async_engine(get_settings().database_url)
        try:
            return await coro_factory(engine)
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def create_schema() -> None:
    async def work(engine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _run(work)


def drop_schema() -> None:
    async def work(engine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    _run(work)


def truncate_all() -> None:
    async def work(engine):
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())

    _run(work)


def count_readings_for(city: str) -> int:
    from sqlalchemy import func, select

    from app.adapters.outbound.persistence.orm import WeatherReadingRow

    async def work(engine):
        async with engine.connect() as conn:
            result = await conn.execute(
                select(func.count())
                .select_from(WeatherReadingRow)
                .where(func.lower(WeatherReadingRow.city) == city.strip().lower())
            )
            return result.scalar_one()

    return _run(work)
