"""The lookup key must collapse the spellings a caller might plausibly use."""

import pytest

from app.domain.city_key import city_key


@pytest.mark.parametrize(
    "name",
    [
        "Timișoara",  # what the geocoder returns
        "Timisoara",  # what a caller is likely to type
        "  TIMISOARA  ",
        "timișoara",
    ],
)
def test_spellings_of_one_city_share_a_key(name):
    assert city_key(name) == "timisoara"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("München", "munchen"),
        ("São Paulo", "sao paulo"),
        ("Bengaluru", "bengaluru"),
        ("Łódź", "łodz"),  # ł has no combining form; only the accent folds
    ],
)
def test_accents_fold_away(name, expected):
    assert city_key(name) == expected


def test_different_cities_keep_different_keys():
    assert city_key("Mumbai") != city_key("Bengaluru")
