# Weather Aggregator Service

A REST service that fetches current weather data from [Open-Meteo](https://open-meteo.com/), stores every reading in PostgreSQL, and serves the saved weather history over HTTP. The application follows Hexagonal Architecture (Ports and Adapters).

Author: Pavan C A  
Repository: [https://github.com/Pavanca2k3/weather-aggregator-service](https://github.com/Pavanca2k3/weather-aggregator-service)

---

## Technology Stack

| Component | Technologies |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Alembic |
| Database | PostgreSQL 16 |
| Frontend | React 19 with Vite |
| Tests | pytest, Pact, Testcontainers, Behave, React Testing Library |

---

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/Pavanca2k3/weather-aggregator-service.git
cd weather-aggregator-service

python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.venv\Scripts\activate
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

### 2. Configure the Database

The application can use any reachable PostgreSQL instance.

Create the local environment file:

```bash
cp .env.example .env
```

On Windows Command Prompt, use:

```cmd
copy .env.example .env
```

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Update the `POSTGRES_*` values in `.env`, and then apply the database migrations:

```bash
alembic upgrade head
```

### Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `POSTGRES_HOST` | `127.0.0.1` | PostgreSQL server host |
| `POSTGRES_PORT` | `5434` | Non-default because port 5432 was occupied during development |
| `POSTGRES_USER` | `nokia_app` | PostgreSQL application user |
| `POSTGRES_PASSWORD` | No default | Required |
| `POSTGRES_DB` | `nokia` | Test suites use `nokia_test` |
| `HTTP_CACHE_ENABLED` | `true` | Enables caching of Open-Meteo responses |
| `HTTP_CACHE_TTL_SECONDS` | `900` | Matches Open-Meteo's refresh cadence |
| `HTTP_RETRIES` | `3` | Retries transient upstream failures |

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

Available URLs:

- **API:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health endpoint:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 4. Run the Frontend

The React UI is optional and runs separately from the backend.

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

Use `localhost` instead of `127.0.0.1` because Vite binds to the IPv6 loopback address in the current development configuration.

The backend must be running on port `8000`. Vite proxies `/api` requests to it, so the frontend does not hardcode a backend port and there is no CORS hop during development.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/weather/fetch?city={city}` | Resolves the city, fetches current conditions, stores the reading, and returns the saved record |
| `GET` | `/weather/{city}` | Returns all stored readings for a city, most recent first |
| `GET` | `/weather/{city}/latest` | Returns only the most recent stored reading |
| `GET` | `/health` | Returns the service and database health status |

### Fetch and Store a Weather Reading

```bash
curl -X POST "http://127.0.0.1:8000/weather/fetch?city=Timisoara"
```

### Example Response

```json
{
  "id": 1,
  "city": "Timișoara",
  "latitude": 45.75372,
  "longitude": 21.22571,
  "temperature_c": 20.56,
  "windspeed_kmh": 10.08,
  "winddirection_deg": 253,
  "weathercode": 1,
  "description": "Mainly clear",
  "is_day": false,
  "observed_at": "2026-09-23T13:30:00Z",
  "fetched_at": "2026-09-23T13:40:51.139479Z"
}
```

### HTTP Status Codes

| Code | When |
|---|---|
| `201 Created` | A weather reading was successfully fetched and stored |
| `200 OK` | Stored weather readings were successfully returned |
| `404 Not Found` | The city could not be resolved or has no stored readings |
| `422 Unprocessable Entity` | The `city` query parameter is missing or empty |
| `502 Bad Gateway` | Open-Meteo is unavailable or returned an unusable response |

---

## Running the Test Suites

Each test tier can be run independently. Only some tiers require supporting infrastructure.

### Run All Python Tests

```bash
pytest
```

This runs every pytest-based tier and normally completes in approximately 30 seconds.

### Run the BDD Scenarios

```bash
behave
```

### Run the Frontend Tests

```bash
cd frontend
npm test
```

### Test Suite Summary

| # | Tier | Command | Requirements | What It Proves |
|---|---|---|---|---|
| 1 | Unit: domain and service | `pytest tests/domain` | None | Business rules using in-memory fakes |
| 2 | Contract: Pact | `pytest tests/contract` | None | The service expectations of Open-Meteo in both directions |
| 3 | Integration: Testcontainers | `pytest tests/integration` | Docker | Repository behavior against a real PostgreSQL container |
| 4 | Component: service tests | `pytest tests/component` | PostgreSQL | Complete flow from HTTP input to database storage and HTTP output |
| 5 | BDD: Behave | `behave` | PostgreSQL | User-facing behavior expressed in Gherkin |
| 6 | UI: React Testing Library | `cd frontend && npm test` | None | React page behavior with `fetch` stubbed |
| 7 | Port conformance | `pytest tests/adapters` | None | Adapters continue to satisfy their ports |

### Run a Single Test

```bash
pytest tests/domain/test_weather_service.py::test_fetch_stores_a_reading
```

### Lint and Format

```bash
ruff check .
ruff format .
```

### Notes on Individual Test Tiers

#### Unit Tests

Unit tests access no database, network, or framework. Both ports are replaced by fakes, so a failure indicates a problem in the domain or application logic.

#### Contract Tests

Contract tests generate Pact files in:

```text
tests/contract/pacts/
```

The generated contracts are replayed against a stub. Two contracts are maintained because the service communicates with two Open-Meteo services:

1. **Geocoding service:** returns JSON and is described field by field.
2. **Forecast service:** uses a recorded response pinned to the expected structure.

No Pact Broker is required.

#### Integration Tests

Integration tests start a real `postgres:16` container and apply the actual Alembic migrations. A broken migration therefore causes the build to fail.

Without Docker, the tests skip cleanly. To run them against a local PostgreSQL database instead, use:

```bash
USE_TESTCONTAINERS=0 pytest tests/integration
```

> **One-time Docker setup per environment:** `niquests`, which is pulled in by the Open-Meteo SDK, depends on `urllib3-future`. It replaces the real `urllib3` at interpreter startup. `docker-py` is incompatible with that fork, so Testcontainers may not reach Docker and the integration tests may skip silently. Run the following command once, and run it again after `pip install -r requirements-dev.txt` because reinstalling `urllib3-future` restores the override:
>
> ```bash
> python scripts/enable_docker_tests.py
> ```

#### Component and BDD Tests

Component and BDD tests share infrastructure from:

```text
tests/support/
```

They reuse the same:

- Open-Meteo stub
- Database helpers
- Application runner

Neither test tier creates separate infrastructure.

---

## Architectural Decisions

### Hexagonal Architecture, Enforced Rather Than Assumed

```text
app/domain/                       Core domain. Pure Python and imports nothing outward.
  models.py                       Coordinates, City, CurrentWeather, WeatherReading
  ports.py                        GeocoderPort, WeatherProviderPort, WeatherRepositoryPort
  service.py                      WeatherService and its use cases
  errors.py                       CityNotFound, NoReadingsForCity, WeatherProviderUnavailable
  weather_codes.py                WMO 4677 lookup
  city_key.py                     City lookup-key normalization

app/adapters/inbound/http/        Drives the application
  routes.py                       HTTP endpoints
  schemas.py                      JSON response schemas
  errors.py                       Domain error to HTTP status mapping
  dependencies.py                 Composition root that binds ports to adapters

app/adapters/outbound/            Driven by the application
  openmeteo/geocoder.py           City name to coordinates
  openmeteo/weather_provider.py   Coordinates to current weather conditions
  openmeteo/session.py            Shared cached and retrying HTTP session
  persistence/orm.py              weather_readings table
  persistence/repository.py       Database rows to and from domain objects

app/db/                           Database engine and session management
app/core/                         Application settings
alembic/                          Database migrations
```

The core declares its requirements using `typing.Protocol` ports. Adapters satisfy those ports structurally and never import them, so every dependency arrow points inward.

Replacing PostgreSQL or Open-Meteo requires a new adapter but does not require changes to the domain code.

This rule is verified by `tests/domain/test_domain_is_pure.py`, which imports the domain in a clean interpreter and fails if a framework appears in `sys.modules`.

### Three Deliberate Shapes for a Reading

`WeatherReading` nests `Coordinates` and `CurrentWeather` because this reflects how the concepts relate in the domain.

The database table flattens them because this is appropriate for relational rows. The JSON response also flattens them because that format is easier for API consumers.

Only two modules translate between these shapes:

- `persistence/repository.py`
- `http/schemas.py`

This separation prevents a database-schema migration from reaching into the domain and prevents a domain refactor from silently changing the public API.

### Two Timestamps per Reading

Open-Meteo recalculates weather data approximately every 15 minutes. Each reading therefore stores two timestamps:

- **`observed_at`:** when Open-Meteo measured the conditions
- **`fetched_at`:** when this service requested them

If the service fetches three times in five minutes, three rows may share the same `observed_at` while having different `fetched_at` values. This distinguishes a weather change from another polling operation.

### Readings Are Append-Only

Every fetch inserts a new row, even when the weather conditions are identical. The table represents a history of polling operations rather than a single current value per city.

Readings are ordered by:

```text
observed_at DESC, fetched_at DESC
```

Therefore, repeated polls for unchanged weather are still returned with the newest fetch first.

### Missing Data Returns 404

`GET /weather/{city}` raises a not-found error when no readings exist instead of returning an empty list.

This prevents a mistyped or unknown city from appearing equivalent to a valid city that happens to have no stored weather history.

### Upstream Failures Return 502

When Open-Meteo is unavailable, the failure comes from an upstream service rather than from this application.

Domain errors are mapped centrally in `http/errors.py`. Routes contain no repeated `try`/`except` blocks, and the domain has no knowledge of HTTP status codes.

### City Lookup Folds Accents and Case

Open-Meteo can return a canonical display name such as `Timișoara` for the input `Timisoara`.

Matching only with `lower(city)` could cause a fetch to succeed and a later lookup to return 404. Each reading therefore includes an accent-folded and case-folded `city_key` that is indexed and used for lookups, while the display name preserves its original diacritics.

### Two Open-Meteo Adapters

Two separate adapters are used because one client library does not support both Open-Meteo calls.

The weather adapter uses the `openmeteo-requests` SDK. Its response values arrive as an unordered list and are matched using each variable's enum tag rather than by position. Positional access could silently swap temperature and wind speed if Open-Meteo changed the response order.

The geocoding service cannot use the same SDK because the geocoding endpoint expects JSON. It therefore uses the JSON API separately.

Both client libraries are synchronous, so the adapters bridge them into the asynchronous application using:

```python
anyio.to_thread.run_sync
```

This technical detail remains outside the core domain.

### Weather Descriptions Are Stored

The WMO 4677 code mapping is defined in the domain, and the resolved weather description is stored with the numeric code.

This keeps historical data readable even if the lookup table is corrected or updated later.

### Caching Does Not Suppress Stored Readings

Open-Meteo responses are cached for 15 minutes using `requests-cache`, with bounded retries through `retry-requests`. This matches Open-Meteo's refresh cadence.

A cached response still creates a new stored reading. This behavior is why `fetched_at` is stored separately from `observed_at`.

Caching can be disabled with:

```env
HTTP_CACHE_ENABLED=false
```

### Transactions Belong to the Request

The `get_db` dependency commits after the request handler returns successfully and rolls back when the handler raises an exception.

The repository therefore calls:

```python
flush()
refresh()
```

It does not call:

```python
commit()
```

Committing inside the repository could partially persist a request that later fails.
