"""WMO 4677 weather codes to human-readable descriptions.

Lives in the domain because the description is part of what a reading *is*,
not a presentation detail: the specification requires it to be stored.
"""

WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Drizzle: light",
    53: "Drizzle: moderate",
    55: "Drizzle: dense",
    56: "Freezing drizzle: light",
    57: "Freezing drizzle: dense",
    61: "Rain: slight",
    63: "Rain: moderate",
    65: "Rain: heavy",
    66: "Freezing rain: light",
    67: "Freezing rain: heavy",
    71: "Snow fall: slight",
    73: "Snow fall: moderate",
    75: "Snow fall: heavy",
    77: "Snow grains",
    80: "Rain showers: slight",
    81: "Rain showers: moderate",
    82: "Rain showers: violent",
    85: "Snow showers: slight",
    86: "Snow showers: heavy",
    95: "Thunderstorm: slight or moderate",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe(weathercode: int) -> str:
    """Human-readable description for a WMO code.

    Unknown codes are reported rather than hidden: Open-Meteo may add codes,
    and a silent "Unknown" would be indistinguishable from a parsing bug.
    """
    return WMO_DESCRIPTIONS.get(weathercode, f"Unknown weather code {weathercode}")
