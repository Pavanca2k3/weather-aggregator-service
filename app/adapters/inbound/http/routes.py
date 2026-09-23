"""The weather endpoints.

Each route does three things and no more: take input, call one use case, shape
the output. There is no business logic here and no try/except -- domain errors
are translated centrally by errors.register_error_handlers.
"""

from fastapi import APIRouter, Depends, Query, status

from app.adapters.inbound.http.dependencies import get_weather_service
from app.adapters.inbound.http.schemas import ErrorOut, WeatherReadingOut
from app.domain.service import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])


@router.post(
    "/fetch",
    response_model=WeatherReadingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Fetch current conditions for a city and store them",
    responses={
        404: {"model": ErrorOut, "description": "City could not be resolved"},
        502: {"model": ErrorOut, "description": "Open-Meteo was unavailable"},
    },
)
async def fetch_weather(
    city: str = Query(..., min_length=1, description="City name, e.g. Bengaluru"),
    service: WeatherService = Depends(get_weather_service),
) -> WeatherReadingOut:
    """Resolve the city, read its current conditions, and save them.

    Always stores a new row: repeated calls build a history rather than
    overwriting, even when Open-Meteo returns unchanged conditions.
    """
    reading = await service.fetch_and_store(city)
    return WeatherReadingOut.from_domain(reading)


@router.get(
    "/{city}",
    response_model=list[WeatherReadingOut],
    summary="All stored readings for a city, most recent first",
    responses={404: {"model": ErrorOut, "description": "No readings stored for this city"}},
)
async def list_readings(
    city: str,
    service: WeatherService = Depends(get_weather_service),
) -> list[WeatherReadingOut]:
    readings = await service.readings_for_city(city)
    return [WeatherReadingOut.from_domain(r) for r in readings]


@router.get(
    "/{city}/latest",
    response_model=WeatherReadingOut,
    summary="The most recent stored reading for a city",
    responses={404: {"model": ErrorOut, "description": "No readings stored for this city"}},
)
async def latest_reading(
    city: str,
    service: WeatherService = Depends(get_weather_service),
) -> WeatherReadingOut:
    reading = await service.latest_for_city(city)
    return WeatherReadingOut.from_domain(reading)
