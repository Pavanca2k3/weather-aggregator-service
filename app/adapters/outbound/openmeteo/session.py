"""Shared HTTP session for the Open-Meteo adapters.

Caching and retrying are adapter concerns: the domain neither knows nor cares
that a response came from a cache. Both are configured here so the geocoder and
the weather provider behave consistently.

The cache TTL defaults to Open-Meteo's own refresh cadence (~15 minutes).
Caching for longer would return conditions the upstream has already replaced;
caching for less just spends requests re-fetching an unchanged reading. Note
this does not suppress rows: a cached response still produces a new stored
reading, which is the point of keeping fetched_at separate from observed_at.
"""

import requests
import requests_cache
from retry_requests import retry

from app.core.config import get_settings


def build_session() -> requests.Session:
    """A session with optional response caching and bounded retries."""
    settings = get_settings()

    if settings.http_cache_enabled:
        session = requests_cache.CachedSession(
            settings.http_cache_path,
            expire_after=settings.http_cache_ttl_seconds,
            allowable_codes=(200,),
        )
    else:
        session = requests.Session()

    # Retry only transient upstream failures; a 404 from geocoding is an answer,
    # not an error to retry.
    return retry(
        session,
        retries=settings.http_retries,
        backoff_factor=settings.http_backoff_factor,
        status_to_retry=(429, 500, 502, 503, 504),
    )
