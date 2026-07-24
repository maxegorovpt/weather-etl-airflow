"""
Extract: pull current weather data from OpenWeatherMap for a list of cities.
"""
import logging
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

CITIES = [
    {"name": "Lisbon", "country": "PT"},
]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def fetch_weather_for_city(city_name: str, country: str, api_key: str) -> dict:
    """Call OpenWeatherMap for a single city. Retries on transient failures."""
    params = {
        "q": f"{city_name},{country}",
        "appid": api_key,
        "units": "metric",  # get Celsius directly, skip manual Kelvin conversion
    }
    response = requests.get(BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def extract_all(api_key: str) -> list[dict]:
    """
    Fetch weather for all tracked cities.
    Returns a list of dicts: {city_name, country, fetched_at, raw_json}
    One city's failure does not stop the others (logged and skipped).
    """
    results = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for city in CITIES:
        try:
            data = fetch_weather_for_city(city["name"], city["country"], api_key)
            results.append(
                {
                    "city_name": city["name"],
                    "country": city["country"],
                    "fetched_at": fetched_at,
                    "raw_json": data,
                }
            )
            logger.info(f"Fetched weather for {city['name']}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch weather for {city['name']}: {e}")
            # Deliberately continue -- one bad city shouldn't fail the whole run.
            continue

    if not results:
        raise RuntimeError("Extract failed for all cities -- aborting DAG run.")

    return results