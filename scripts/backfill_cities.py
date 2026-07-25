"""
One-time backfill: pull ~3 years of hourly historical weather for every
city in dim_city from the Open-Meteo Archive API (free, no API key needed)
and load it into fact_weather.

Run this ONCE from your host machine (not inside Airflow):
    python3 scripts/backfill_cities.py

Requires: requests, psycopg2-binary  (pip install requests psycopg2-binary)
"""
import sys
import time
from datetime import date, timedelta

import psycopg2
import requests
from psycopg2.extras import execute_values

# Connect via the HOST-mapped port (5433), since this runs on your machine, not in Docker
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "weather",
    "user": "weather_user",
    "password": "weather_pass",
}

# WMO weather code -> detailed description (maps to weather_desc)
WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

# WMO weather code -> short category (matches OpenWeatherMap's "main" granularity)
WEATHER_MAIN_CODES = {
    0: "Clear", 1: "Clouds", 2: "Clouds", 3: "Clouds",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    56: "Drizzle", 57: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Rain",
    66: "Rain", 67: "Rain",
    71: "Snow", 73: "Snow", 75: "Snow",
    77: "Snow",
    80: "Rain", 81: "Rain", 82: "Rain",
    85: "Snow", 86: "Snow",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}


def fetch_historical(lat: float, lon: float, start: date, end: date) -> dict:
    """Fetch one date range of hourly data from Open-Meteo Archive API."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                  "surface_pressure,wind_speed_10m,weathercode",
        "timezone": "UTC",
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def to_rows(data: dict, city_id: int) -> list[tuple]:
    """Flatten Open-Meteo's parallel-array response into fact_weather rows."""
    hourly = data["hourly"]
    rows = []
    for i, ts in enumerate(hourly["time"]):
        temp = hourly["temperature_2m"][i]
        if temp is None:
            continue
        code = hourly["weathercode"][i]
        rows.append(
            (
                city_id,
                ts,
                temp,
                hourly["apparent_temperature"][i],
                hourly["relative_humidity_2m"][i],
                hourly["surface_pressure"][i],
                hourly["wind_speed_10m"][i],
                WEATHER_MAIN_CODES.get(code, "Unknown"),
                WEATHER_CODES.get(code, "Unknown"),
            )
        )
    return rows


def load_rows(conn, rows: list[tuple]) -> None:
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO fact_weather
                (city_id, observed_at, temp_c, feels_like_c, humidity,
                 pressure, wind_speed, weather_main, weather_desc)
            VALUES %s
            ON CONFLICT (city_id, observed_at) DO NOTHING
            """,
            rows,
        )
    conn.commit()


def main():
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=365 * 3)

    conn = psycopg2.connect(**DB_CONFIG)

    with conn.cursor() as cur:
        cur.execute("SELECT city_id, city_name, lat, lon FROM dim_city ORDER BY city_name")
        cities = cur.fetchall()

    if not cities:
        print("No cities found in dim_city -- run create_tables.sql first.")
        sys.exit(1)

    print(f"Backfilling {len(cities)} cities from {start} to {end}...\n")

    for city_id, city_name, lat, lon in cities:
        print(f"[{city_name}] fetching {start} -> {end}")
        all_rows = []
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + timedelta(days=365), end)
            data = fetch_historical(lat, lon, chunk_start, chunk_end)
            all_rows.extend(to_rows(data, city_id))
            chunk_start = chunk_end + timedelta(days=1)
            time.sleep(0.5)  # be polite to the free API

        load_rows(conn, all_rows)
        print(f"[{city_name}] loaded {len(all_rows)} rows\n")

    conn.close()
    print("Backfill complete for all cities.")


if __name__ == "__main__":
    main()