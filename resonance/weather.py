from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

# Approximate location from the public IP address; only used if the user
# chooses to share their location.
IP_LOCATION_URL = "https://ipinfo.io/json"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_REFRESH_TIME: int = 15 * 60

CLOUD = ("     .--.    ", "  .-(    ).  ", " (___.__)__) ")
ICONS: dict[str, tuple[str, ...]] = {
    "clear": (
        "   \\   /   ",
        "    .-.    ",
        " - (   ) - ",
        "    `-'    ",
        "   /   \\   ",
    ),
    "moon": (
        "    .--.     ",
        "   /  .-'    ",
        "  |  (       ",
        "   \\  '-.    ",
        "    '--'     ",
    ),
    "partly": (
        "  \\  /      ",
        "_ /\"\".-.    ",
        "  \\_(   ).  ",
        "  /(___(__) ",
        "            ",
    ),
    "cloudy": ("             ", *CLOUD, "             "),
    "fog": (
        "             ",
        " _ - _ - _ - ",
        "  _ - _ - _  ",
        " _ - _ - _ - ",
        "             ",
    ),
    "rain": (*CLOUD, "   ' ' ' '   ", "  ' ' ' '    "),
    "snow": (*CLOUD, "   *  *  *   ", "  *  *  *    "),
    "thunder": (*CLOUD, "    /_  /_   ", "     /   /   "),
}


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> Location | None:
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                str(data["name"]),
                float(data["latitude"]),
                float(data["longitude"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


def fetch_json(url: str) -> Any:
    with urlopen(url, timeout=8) as response:
        return json.load(response)


def locate_by_ip() -> Location:
    data = fetch_json(IP_LOCATION_URL)
    latitude, longitude = (float(part) for part in data["loc"].split(","))
    return Location(data.get("city") or "your area", latitude, longitude)


def search_city(name: str) -> Location | None:
    data = fetch_json(
        f"{GEOCODING_URL}?{urlencode({'name': name, 'count': 1})}"
    )
    results = data.get("results") or []
    if not results:
        return None
    place = results[0]
    return Location(place["name"], place["latitude"], place["longitude"])


def describe(code: int, is_day: bool = True) -> tuple[str, str]:
    """Map a WMO weather code to (description, icon name)."""
    if code == 0:
        return "clear", "clear" if is_day else "moon"
    if code in (1, 2):
        return "partly cloudy", "partly" if is_day else "cloudy"
    if code == 3:
        return "overcast", "cloudy"
    if code in (45, 48):
        return "fog", "fog"
    if 51 <= code <= 57:
        return "drizzle", "rain"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "rain", "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow", "snow"
    if code >= 95:
        return "thunderstorm", "thunder"
    return "unknown", "cloudy"


def get_weather(location: Location) -> dict[str, Any]:
    query = urlencode(
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": "temperature_2m,apparent_temperature,weather_code,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset",
            "forecast_days": 1,
            "timezone": "auto",
        }
    )
    data = fetch_json(f"{FORECAST_URL}?{query}")
    current = data["current"]
    description, icon = describe(
        int(current["weather_code"]),
        bool(current.get("is_day", 1)),
    )
    return {
        "location": location.name,
        "temperature": round(current["temperature_2m"]),
        "feels_like": round(current["apparent_temperature"]),
        "high": round(data["daily"]["temperature_2m_max"][0]),
        "low": round(data["daily"]["temperature_2m_min"][0]),
        "description": description,
        "icon": ICONS[icon],
        # Local times at the location, like "2026-10-14T07:45".
        "sunrise": data["daily"]["sunrise"][0],
        "sunset": data["daily"]["sunset"][0],
    }
