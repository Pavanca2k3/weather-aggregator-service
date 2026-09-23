"""A real PostgreSQL, started once per test session with Testcontainers.

The integration suite is not allowed to mock the database layer, so it needs a
genuine server. Testcontainers gives every run a private, empty one instead of
relying on whatever happens to be listening on port 5434.

Two rules shape this module:

* Nothing here may import an app module. ``app.db.session`` builds its engine at
  import time from settings, so the container has to be running and the
  ``POSTGRES_*`` variables exported *before* the first app import happens.
* Failure is a skip, not an error. A machine without Docker should be told so
  plainly, and ``USE_TESTCONTAINERS=0`` remains an escape hatch for running the
  suite against a locally provisioned database.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Pinned rather than :latest so a run cannot silently change its own database
# version; it is also the image the compose file and CI already use.
POSTGRES_IMAGE = os.getenv("TESTCONTAINERS_POSTGRES_IMAGE", "postgres:16")

_FALSEY = {"0", "false", "no", "off", ""}

_container = None
_started = False
_skip_reason: str | None = None


def testcontainers_enabled() -> bool:
    """False when the caller has opted out via ``USE_TESTCONTAINERS=0``."""
    return os.getenv("USE_TESTCONTAINERS", "1").strip().lower() not in _FALSEY


def container_in_use() -> bool:
    """True only once a container is actually running for this process."""
    return _container is not None


def start_postgres() -> str | None:
    """Start the container and export its connection details.

    Returns ``None`` on success, or a human-readable reason the integration
    tests should be skipped. Never raises: an unusable Docker is a skip.
    """
    global _container, _started

    if _started:
        return None if _container is not None else _skip_reason
    _started = True

    if not testcontainers_enabled():
        # Opted out: fall back to the developer's local database, keeping the
        # dedicated test database name the suite has always used.
        os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "nokia_test")
        return None

    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:  # pragma: no cover - depends on the installed extras
        try:
            from testcontainers.postgres import PostgresContainer  # type: ignore[no-redef]
        except ImportError as exc:
            return _skip(
                "testcontainers is not installed -- "
                f"run `pip install -r requirements-dev.txt` ({exc}). "
                "Set USE_TESTCONTAINERS=0 to use a local PostgreSQL on port 5434 instead."
            )

    try:
        # Credentials are spelled out rather than left to default, because
        # PostgresContainer otherwise picks them up from POSTGRES_USER and
        # friends -- the very variables this function is about to overwrite.
        # Constructing it already talks to the daemon, so it is inside the try.
        container = PostgresContainer(
            image=POSTGRES_IMAGE,
            username="nokia_test",
            password="nokia_test",
            dbname="nokia_test",
        )
        container.start()
    except Exception as exc:  # noqa: BLE001 - any Docker failure means "skip"
        return _skip(
            f"could not start the {POSTGRES_IMAGE} test container -- "
            f"is Docker running? ({type(exc).__name__}: {exc}). "
            "Set USE_TESTCONTAINERS=0 to use a local PostgreSQL on port 5434 instead."
        )

    _container = container
    atexit.register(stop_postgres)

    # Exported, not passed around: settings are built from the environment and
    # the app reads them the moment it is imported.
    os.environ["POSTGRES_HOST"] = container.get_container_host_ip()
    os.environ["POSTGRES_PORT"] = str(container.get_exposed_port(5432))
    os.environ["POSTGRES_USER"] = container.username
    os.environ["POSTGRES_PASSWORD"] = container.password
    os.environ["POSTGRES_DB"] = container.dbname
    return None


def _skip(reason: str) -> str:
    global _skip_reason
    _skip_reason = reason
    return reason


def stop_postgres() -> None:
    """Idempotent: the fixture stops the container, atexit is the safety net."""
    global _container
    container, _container = _container, None
    if container is not None:
        container.stop()


def run_migrations() -> None:
    """Bring the container's database up to head with the real migrations.

    Running Alembic rather than ``Base.metadata.create_all`` means the schema the
    tests exercise is the schema a deployment would get, so a broken migration
    fails here instead of in production.

    A subprocess, because ``alembic/env.py`` drives its async engine with
    ``asyncio.run()`` and would refuse to start inside the suite's own loop.
    """
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed against the test container:\n"
            f"{result.stdout}\n{result.stderr}"
        )
