"""Component (service) tests: the whole application, with Open-Meteo stubbed out.

Nothing inside the app is patched or overridden. The application runs in its own
process-local server, talks to a real PostgreSQL, and reaches a stub Open-Meteo
only because `OPENMETEO_*_URL` settings point there. Each test drives the public
REST API over HTTP and then asserts *both* halves of the contract: the response
that came back, and the rows that actually landed in the database.
"""

from datetime import UTC, datetime

import pytest

BENGALURU = "Bengaluru"
LATITUDE = 12.97194
LONGITUDE = 77.59369

# The recorded flatbuffers forecast the stub replays
# (tests/contract/fixtures/forecast_current_weather.bin) always reports these
# conditions, so every expectation below is fixed rather than weather-dependent.
OBSERVED_AT = datetime.fromtimestamp(1790172000, UTC)  # 2026-09-23T14:00:00Z
TEMPERATURE_C = 23.55  # Numeric(5, 2) in the table, so the raw 23.5499... rounds
WINDSPEED_KMH = 18.91
WINDDIRECTION_DEG = 254
WEATHERCODE = 3
DESCRIPTION = "Overcast"  # WMO 4677 for code 3


@pytest.fixture
def known_city(stub):
    """The upstream knows Bengaluru; nothing else."""
    stub.set_city(BENGALURU, latitude=LATITUDE, longitude=LONGITUDE)
    return BENGALURU


def fetch(client, city):
    return client.post("/weather/fetch", params={"city": city})


# ---------------------------------------------------------------- the flow ---


def test_fetch_stores_a_row_and_returns_201_with_the_reading(client, db, stub, known_city):
    response = fetch(client, known_city)

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["city"] == BENGALURU
    assert body["latitude"] == pytest.approx(LATITUDE)
    assert body["longitude"] == pytest.approx(LONGITUDE)
    assert body["temperature_c"] == pytest.approx(TEMPERATURE_C)
    assert body["windspeed_kmh"] == pytest.approx(WINDSPEED_KMH)
    assert body["winddirection_deg"] == WINDDIRECTION_DEG
    assert body["weathercode"] == WEATHERCODE
    assert body["description"] == DESCRIPTION
    assert body["is_day"] is False
    assert datetime.fromisoformat(body["observed_at"]) == OBSERVED_AT
    assert isinstance(body["id"], int)

    # HTTP in -> DB stored: the row exists and carries what the response claimed
    assert db.count_readings_for(BENGALURU) == 1
    (row,) = db.rows_for(BENGALURU)
    assert row["id"] == body["id"]
    assert row["city"] == BENGALURU
    assert float(row["temperature_c"]) == pytest.approx(TEMPERATURE_C)
    assert float(row["windspeed_kmh"]) == pytest.approx(WINDSPEED_KMH)
    assert row["winddirection_deg"] == WINDDIRECTION_DEG
    assert row["weathercode"] == WEATHERCODE
    assert row["description"] == DESCRIPTION
    assert row["is_day"] is False
    assert row["observed_at"] == OBSERVED_AT
    # fetched_at is when we asked, observed_at when the provider measured
    assert row["fetched_at"] >= row["observed_at"]

    # and it really went through the stub, not the internet
    assert any("/v1/search" in seen for seen in stub.requests_seen)
    assert any("/v1/forecast" in seen for seen in stub.requests_seen)


def test_the_stored_reading_is_retrievable_via_get_city(client, db, known_city):
    created = fetch(client, known_city).json()

    response = client.get(f"/weather/{known_city}")

    assert response.status_code == 200, response.text
    readings = response.json()
    assert [r["id"] for r in readings] == [created["id"]]
    assert readings[0] == created
    assert db.count_readings_for(BENGALURU) == 1


def test_latest_returns_the_newest_reading(client, db, known_city):
    first = fetch(client, known_city).json()
    second = fetch(client, known_city).json()
    third = fetch(client, known_city).json()

    response = client.get(f"/weather/{known_city}/latest")

    assert response.status_code == 200, response.text
    latest = response.json()
    assert latest["id"] == third["id"]
    assert latest["id"] not in {first["id"], second["id"]}
    # the other two are still there -- "latest" is a view, not a replacement
    assert db.count_readings_for(BENGALURU) == 3


def test_repeated_fetches_accumulate_rows(client, db, known_city):
    ids = [fetch(client, known_city).json()["id"] for _ in range(3)]

    assert len(set(ids)) == 3
    assert db.count_readings_for(BENGALURU) == 3

    rows = db.rows_for(BENGALURU)
    assert sorted(row["id"] for row in rows) == sorted(ids)
    # identical upstream conditions are kept, not de-duplicated
    assert {row["observed_at"] for row in rows} == {OBSERVED_AT}

    listed = client.get(f"/weather/{known_city}").json()
    assert len(listed) == 3
    fetched_at = [r["fetched_at"] for r in listed]
    assert fetched_at == sorted(fetched_at, reverse=True), "not newest-first"


def test_the_response_carries_a_human_readable_description(client, db, known_city):
    body = fetch(client, known_city).json()

    assert body["weathercode"] == 3
    assert body["description"] == "Overcast"
    # stored too, so history stays readable without re-deriving it
    assert db.rows_for(BENGALURU)[0]["description"] == "Overcast"
    assert client.get(f"/weather/{known_city}/latest").json()["description"] == "Overcast"


def test_city_lookup_is_case_insensitive(client, db, known_city):
    created = fetch(client, "bengaluru").json()
    # stored under the geocoder's canonical spelling, not what the caller typed
    assert created["city"] == BENGALURU

    for spelling in ("BENGALURU", "bengaluru", "BeNgAlUrU"):
        listed = client.get(f"/weather/{spelling}")
        assert listed.status_code == 200, listed.text
        assert [r["id"] for r in listed.json()] == [created["id"]]

        latest = client.get(f"/weather/{spelling}/latest")
        assert latest.status_code == 200, latest.text
        assert latest.json()["id"] == created["id"]

        assert db.count_readings_for(spelling) == 1


# ------------------------------------------------------------- the failures ---


def test_an_unresolvable_city_is_404_and_stores_nothing(client, db, known_city):
    response = fetch(client, "Atlantis")

    assert response.status_code == 404, response.text
    assert "Atlantis" in response.json()["detail"]
    assert db.count_readings_for("Atlantis") == 0
    assert db.rows_for("Atlantis") == []
    # and the known city was not touched either
    assert db.count_readings_for(BENGALURU) == 0


def test_an_upstream_forecast_failure_is_502_and_stores_nothing(client, db, stub, known_city):
    stub.fail_forecast_with(503)

    response = fetch(client, known_city)

    assert response.status_code == 502, response.text
    assert db.count_readings_for(BENGALURU) == 0
    assert db.rows_for(BENGALURU) == []

    # the city resolved fine; it was the forecast that failed
    assert any("/v1/search" in seen for seen in stub.requests_seen)
    assert any("/v1/forecast" in seen for seen in stub.requests_seen)


def test_reading_a_city_with_no_stored_rows_is_404_not_an_empty_list(client, db, known_city):
    assert db.count_readings_for(BENGALURU) == 0

    assert client.get(f"/weather/{known_city}").status_code == 404
    assert client.get(f"/weather/{known_city}/latest").status_code == 404
