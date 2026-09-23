"""Provider verification: replay the pact files against a stub.

The consumer tests wrote down what this service expects. These tests prove a
provider *can* satisfy those expectations, by replaying every recorded
interaction against a stub that serves the documented shapes.

No Pact Broker: the pacts are read straight off disk.
"""

import pytest
from pact import Verifier

from tests.contract.conftest import FORECAST_PROVIDER, GEOCODING_PROVIDER, PACT_DIR
from tests.contract.stub_provider import StubProvider

PACT_FILES = {
    GEOCODING_PROVIDER: PACT_DIR / "weather-aggregator-open-meteo-geocoding.json",
    FORECAST_PROVIDER: PACT_DIR / "weather-aggregator-open-meteo-forecast.json",
}


@pytest.fixture
def stub():
    with StubProvider() as server:
        yield server


@pytest.mark.parametrize("provider", list(PACT_FILES))
def test_stub_satisfies_the_contract(provider, stub):
    pact_file = PACT_FILES[provider]
    assert pact_file.exists(), (
        f"{pact_file.name} is missing -- run the consumer tests first, they are what generate it"
    )

    verifier = (
        Verifier(provider, host="127.0.0.1")
        .add_transport(url=stub.url)
        .add_source(pact_file)
        # the stub is stateless; states are acknowledged at this endpoint
        .state_handler(f"{stub.url}/_pact/provider_states", teardown=False, body=True)
        .set_error_on_empty_pact(enabled=True)
    )

    verifier.verify()
