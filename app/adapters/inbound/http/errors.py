"""Translates domain errors into HTTP responses.

The core raises meaningful exceptions and knows nothing about status codes;
this module is where that knowledge lives. Registering handlers centrally keeps
every route free of try/except blocks.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.errors import CityNotFound, NoReadingsForCity, WeatherProviderUnavailable

# Domain error -> status code. Both "not found" cases are 404: a city we cannot
# resolve and a city with no stored readings are, from the caller's side, both
# "there is nothing here". Returning an empty list instead would hide a typo.
ERROR_STATUS = {
    CityNotFound: status.HTTP_404_NOT_FOUND,
    NoReadingsForCity: status.HTTP_404_NOT_FOUND,
    # the upstream provider failed, not this service: 502 rather than 500
    WeatherProviderUnavailable: status.HTTP_502_BAD_GATEWAY,
}


def register_error_handlers(app: FastAPI) -> None:
    for error_type, status_code in ERROR_STATUS.items():
        app.add_exception_handler(error_type, _make_handler(status_code))


def _make_handler(status_code: int):
    async def handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler
