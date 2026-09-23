"""Step definitions.

Every step goes through the running application over HTTP, or reads the
database directly to assert what was actually persisted. No step reaches into
application internals.
"""

from behave import given, then, when

# ---------------------------------------------------------------- given -----


@given('the weather service knows about "{city}" at {lat:f}, {lon:f}')
def step_known_city(context, city, lat, lon):
    context.stub.set_city(city, latitude=lat, longitude=lon)


@given("no readings are stored")
def step_no_readings(context):
    context.database.truncate_all()


@given("the upstream weather service is failing with {status:d}")
def step_upstream_failing(context, status):
    context.stub.fail_forecast_with(status)


@given('I have fetched the weather for "{city}" {count:d} times')
def step_prefetch(context, city, count):
    for _ in range(count):
        response = context.client.post("/weather/fetch", params={"city": city})
        assert response.status_code == 201, f"setup fetch failed: {response.text}"


# ----------------------------------------------------------------- when -----


@when('I fetch the weather for "{city}"')
def step_fetch(context, city):
    context.response = context.client.post("/weather/fetch", params={"city": city})


@when('I ask for the readings for "{city}"')
def step_get_readings(context, city):
    context.response = context.client.get(f"/weather/{city}")


@when('I ask for the latest reading for "{city}"')
def step_get_latest(context, city):
    context.response = context.client.get(f"/weather/{city}/latest")


# ----------------------------------------------------------------- then -----


@then("the response status is {status:d}")
def step_status(context, status):
    assert context.response.status_code == status, (
        f"expected {status}, got {context.response.status_code}: {context.response.text}"
    )


@then('the response is for the city "{city}"')
def step_response_city(context, city):
    body = context.response.json()
    payload = body[0] if isinstance(body, list) else body
    assert payload["city"] == city, f"expected city {city!r}, got {payload['city']!r}"


@then('{count:d} reading is stored for "{city}"')
@then('{count:d} readings are stored for "{city}"')
def step_count_stored(context, count, city):
    actual = context.database.count_readings_for(city)
    assert actual == count, f"expected {count} stored for {city!r}, found {actual}"


@then('no readings are stored for "{city}"')
def step_none_stored(context, city):
    actual = context.database.count_readings_for(city)
    assert actual == 0, f"expected nothing stored for {city!r}, found {actual}"


@then("all stored readings share the same observation time")
def step_same_observation(context):
    readings = context.client.get("/weather/Bengaluru").json()
    observed = {r["observed_at"] for r in readings}
    assert len(observed) == 1, f"expected one observation time, got {observed}"


@then("the readings are ordered most recent first")
def step_ordering(context):
    readings = context.client.get("/weather/Bengaluru").json()
    fetched = [r["fetched_at"] for r in readings]
    assert fetched == sorted(fetched, reverse=True), f"not newest-first: {fetched}"
