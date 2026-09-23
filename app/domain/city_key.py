"""Normalising city names for lookup.

Geocoders return the local spelling -- Open-Meteo answers "Timisoara" with
"Timișoara" -- so storing the canonical name and matching on `lower(city)`
means a caller who fetched with an ASCII name cannot read it back. Folding
accents away gives one key both spellings share, while the display name keeps
its diacritics.
"""

import unicodedata


def city_key(name: str) -> str:
    """A lookup key: accent-folded, case-folded, whitespace-trimmed.

    "Timișoara", "Timisoara" and "  TIMISOARA " all key to "timisoara".
    """
    decomposed = unicodedata.normalize("NFKD", name.strip())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.casefold()
