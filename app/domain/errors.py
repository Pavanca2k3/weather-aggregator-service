"""Domain errors.

The core raises these; it never raises HTTPException and never returns a status
code. Translating them into HTTP responses is the inbound adapter's job, which
is what keeps the core independent of FastAPI.
"""


class DomainError(Exception):
    """Base class for every error the domain raises."""


class CityNotFound(DomainError):
    """The geocoder could not resolve the given name to a location."""

    def __init__(self, city: str) -> None:
        self.city = city
        super().__init__(f"Could not resolve city: {city!r}")


class NoReadingsForCity(DomainError):
    """No readings have been stored for this city yet.

    Raised instead of returning an empty list so the API reports a clear 404
    rather than an empty success that hides a typo'd city name.
    """

    def __init__(self, city: str) -> None:
        self.city = city
        super().__init__(f"No stored readings for city: {city!r}")


class WeatherProviderUnavailable(DomainError):
    """The upstream weather provider failed or returned something unusable."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Weather provider unavailable: {reason}")
