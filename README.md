# Weather Aggregator Service

A small REST service that fetches current weather from [Open-Meteo](https://open-meteo.com),
stores each reading in PostgreSQL, and exposes the saved history over HTTP.

Built with **Hexagonal Architecture (Ports & Adapters)** — the business logic has no idea that
FastAPI, PostgreSQL or Open-Meteo exist.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/weather/fetch?city={city}` | Resolve the city, fetch current conditions, store and return the saved record |
| `GET` | `/weather/{city}` | All stored readings for a city, most recent first |
| `GET` | `/weather/{city}/latest` | Only the most recent reading |
| `GET` | `/health` | Service + database health |

Interactive docs at `/docs` once running.

### Example

```bash
curl -X POST "http://127.0.0.1:8000/weather/fetch?city=bengaluru"
```

```json
{
  "id": 1,
  "city": "Bengaluru",
  "latitude": 12.97194,
  "longitude": 77.59369,
  "temperature_c": 22.8,
  "windspeed_kmh": 14.42,
  "winddirection_deg": 267,
  "weathercode": 3,
  "is_day": false,
  "observed_at": "2026-09-22T16:15:00Z",
  "fetched_at": "2026-09-22T16:27:50.420458Z"
}
```

City names are **case-insensitive** and stored under the geocoder's canonical spelling, so
`bengaluru` and `BENGALURU` build one history rather than three.

### Status codes

| Code | When |
|---|---|
| `201` | Reading fetched and stored |
| `200` | Readings returned |
| `404` | City cannot be resolved, or has no stored readings |
| `422` | Missing or empty `city` parameter |
| `502` | Open-Meteo was unreachable or returned something unusable |

Absent data returns **404, not an empty list** — a mistyped city should not look like a city with
no weather.

---

## Why two timestamps?

Open-Meteo only refreshes roughly every 15 minutes, so each reading carries both:

- **`observed_at`** — when Open-Meteo measured the conditions
- **`fetched_at`** — when this service asked for them

Call `/weather/fetch` three times in five minutes and you get three rows sharing one `observed_at`.
That distinguishes *"the weather changed"* from *"I polled again"*. Every fetch is stored; the
table is an append-only history, never an overwrite.

---

## Architecture

```
app/domain/                       ← the core. Pure Python, imports nothing outward.
  models.py                         Coordinates, City, CurrentWeather, WeatherReading
  ports.py                          GeocoderPort, WeatherProviderPort, WeatherRepositoryPort
  service.py                        WeatherService — the use cases
  errors.py                         CityNotFound, NoReadingsForCity, WeatherProviderUnavailable

app/adapters/inbound/http/        ← drives the app
  routes.py                         the three endpoints
  schemas.py                        JSON response shapes
  errors.py                         domain error → HTTP status
  dependencies.py                   composition root (binds ports to adapters)

app/adapters/outbound/            ← driven by the app
  openmeteo/geocoder.py             city name → coordinates
  openmeteo/weather_provider.py     coordinates → current conditions
  openmeteo/session.py              shared cached + retrying HTTP session
  persistence/orm.py                the weather_readings table
  persistence/repository.py         rows ↔ domain objects

app/db/, app/core/                ← engine, session, settings
alembic/                          ← migrations
```

**The rule:** dependency arrows point *inward*. The core declares what it needs as `Protocol`
ports; adapters satisfy them structurally and never import them. Swapping PostgreSQL or Open-Meteo
means writing a new adapter and changing no domain code.

A test enforces this — `tests/domain/test_domain_is_pure.py` fails the build if anything in
`app/domain/` ever imports a framework.

---

## Setup

Requires Python 3.11+ and PostgreSQL.

```bash
git clone https://github.com/vishnu242022/weather-aggregator-service.git
cd weather-aggregator-service

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements-dev.txt
```

Create a database and point the app at it:

```bash
cp .env.example .env            # then edit the POSTGRES_* values
alembic upgrade head
```

### Configuration

| Variable | Default | Notes |
|---|---|---|
| `POSTGRES_HOST` | `127.0.0.1` | |
| `POSTGRES_PORT` | `5434` | not 5432 — see below |
| `POSTGRES_USER` | `nokia_app` | |
| `POSTGRES_PASSWORD` | — | required |
| `POSTGRES_DB` | `nokia` | tests use `nokia_test` |
| `HTTP_CACHE_ENABLED` | `true` | cache Open-Meteo responses |
| `HTTP_CACHE_TTL_SECONDS` | `900` | matches Open-Meteo's refresh cadence |
| `HTTP_RETRIES` | `3` | retries on transient upstream failures |

> This project runs its own PostgreSQL cluster on **port 5434** because 5432/5433 were already
> taken on the development machine. Any reachable PostgreSQL works — just set the variables above.
> A helper script, `scripts/pg.ps1` (`start` / `stop` / `status` / `psql` / `log`), manages the
> local cluster on Windows.

---

## Run

```bash
uvicorn app.main:app --reload
```

- API — http://127.0.0.1:8000
- Docs — http://127.0.0.1:8000/docs

---

## Tests

```bash
pytest                    # every Python tier, ~30s
behave                    # BDD scenarios against the running app
cd frontend && npm test   # React Testing Library
```

| Tier | Command | Needs | What it proves |
|---|---|---|---|
| Unit (domain) | `pytest tests/domain` | nothing | business rules, on in-memory fakes |
| Port conformance | `pytest tests/adapters` | nothing | adapters still satisfy the ports |
| Contract (Pact) | `pytest tests/contract` | nothing | what we expect of Open-Meteo, both directions |
| Integration | `pytest tests/integration` | Docker | the repository against a real PostgreSQL container |
| Component | `pytest tests/component` | PostgreSQL | full app, HTTP in -> DB stored -> HTTP out |
| BDD | `behave` | PostgreSQL | user-facing behaviour in Gherkin |
| UI | `npm test` | nothing | the React page, fetch stubbed |

The split matters. Domain tests run on in-memory fakes with no database and no internet. Every
tier above them stubs Open-Meteo, so nothing fails because the weather changed or the network
dropped.

### Testcontainers and a urllib3 conflict

`pytest tests/integration` starts a real `postgres:16` container and runs the actual Alembic
migrations against it, so a broken migration fails the build.

One snag worth knowing: `niquests` (pulled in by the Open-Meteo SDK) depends on `urllib3-future`,
which **replaces the real `urllib3` package at interpreter start**. `docker-py` breaks against that
fork, so Testcontainers cannot reach Docker and every integration test skips. Fix it once per
environment:

```bash
python scripts/enable_docker_tests.py
```

Re-run it after any `pip install -r requirements-dev.txt`, since reinstalling `urllib3-future`
restores the override. Without Docker the integration tests skip cleanly; `USE_TESTCONTAINERS=0`
runs them against a local PostgreSQL instead.

---

## Development

```bash
ruff check .                                       # lint
ruff format .                                      # format
alembic revision --autogenerate -m "description"   # new migration
alembic upgrade head
```

---

## Notes

- Only Open-Meteo's `current_weather` block is used — no forecast, no hourly data.
- The weather adapter uses the `openmeteo-requests` SDK. Its flatbuffer responses list values
  without a guaranteed order, so they are matched by each variable's enum tag rather than by index.
- The geocoder uses plain JSON, because Open-Meteo's geocoding endpoint rejects the SDK's protobuf
  format.
- Responses are cached for 15 minutes (`requests-cache`) with bounded retries (`retry-requests`),
  matching Open-Meteo's refresh cadence. Caching does not suppress rows: a cached response still
  produces a new stored reading, which is the point of tracking `fetched_at` separately.
  Disable with `HTTP_CACHE_ENABLED=false`.

---

## Frontend

A minimal React UI lives in `frontend/`. It has one input and two actions: fetch a city's current
weather and store it, or load what is already stored.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The backend must be running on port 8000. Vite proxies `/api` to it (see `vite.config.js`), so the
frontend never hardcodes the backend port and there is no CORS hop in development.

The readings table shows `observed_at` and `fetched_at` side by side, which makes the append-only
behaviour visible: poll the same city twice inside 15 minutes and you get two rows sharing one
observation time.
