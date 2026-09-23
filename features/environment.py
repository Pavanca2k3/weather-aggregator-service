"""Behave lifecycle.

Builds exactly one set of infrastructure for the whole run -- the same stub and
the same database helpers the component tests use -- and points the real
application at it through settings. Nothing inside the app is patched.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def before_all(context):
    from tests.support.openmeteo_stub import OpenMeteoStub

    context.stub = OpenMeteoStub().start()

    # Settings are read at import time, so every environment variable must be
    # in place before any app module is imported.
    os.environ["POSTGRES_DB"] = os.getenv("TEST_POSTGRES_DB", "nokia_test")
    os.environ["OPENMETEO_GEOCODING_URL"] = context.stub.geocoding_url
    os.environ["OPENMETEO_FORECAST_URL"] = context.stub.forecast_url
    # a cache would let one scenario's upstream answer leak into the next
    os.environ["HTTP_CACHE_ENABLED"] = "false"

    from tests.support import database
    from tests.support.app_server import AppServer

    context.database = database
    database.create_schema()

    context.server = AppServer().start()
    context.client = context.server.client()


def before_scenario(context, scenario):
    context.stub.reset()
    context.database.truncate_all()
    context.response = None


def after_all(context):
    if getattr(context, "client", None):
        context.client.close()
    if getattr(context, "server", None):
        context.server.stop()
    if getattr(context, "database", None):
        context.database.drop_schema()
    if getattr(context, "stub", None):
        context.stub.stop()
