"""
Extract: pull current weather data from OpenWeatherMap for a list of cities.
"""
import logging
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Germany's 10 biggest cities by population
CITIES = [
    {"name": "Berlin", "country": "DE"},
    {"name": "Hamburg", "country": "DE"},
    {"name": "Munich", "country": "DE"},
    {"name": "Cologne", "country": "DE"},
    {"name": "Frankfurt", "country": "DE"},
    {"name": "Stuttgart", "country": "DE"},
    {"name": "Dusseldorf", "country": "DE"},
    {"name": "Leipzig", "country": "DE"},
    {"name": "Dortmund", "country": "DE"},
    {"name": "Essen", "country": "DE"},
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
        "units": "metric",
    }
    response = requests.get(BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def extract_all(api_key: str) -> list[dict]:
    """
    Fetch weather for all tracked cities.
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
            continue

    if not results:
        raise RuntimeError("Extract failed for all cities -- aborting DAG run.")

    return results