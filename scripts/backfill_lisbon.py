"""
One-time backfill: pull ~3 years of hourly historical weather for Lisbon
from the Open-Meteo Archive API (free, no API key needed) and load it
into fact_weather.

Run this ONCE from your host machine (not inside Airflow):
    python3 scripts/backfill_lisbon.py

Requires: requests, psycopg2-binary  (pip install requests psycopg2-binary)
"""
import sys
from datetime import date, timedelta

import psycopg2
import requests
from psycopg2.extras import execute_values

LAT, LON = 38.7223, -9.1393
CITY_NAME = "Lisbon"

# Connect via the HOST-mapped port (5433), since this runs on your machine, not in Docker
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "weather",
    "user": "weather_user",
    "password": "weather_pass",
}

# WMO weather code -> human-readable description
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


def fetch_historical(start: date, end: date) -> dict:
    """Fetch one date range of hourly data from Open-Meteo Archive API."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LAT,
        "longitude": LON,
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
            continue  # skip gaps in the historical record
        code = hourly["weathercode"][i]
        rows.append(
            (
                city_id,
                ts,  # ISO string, Postgres will cast to timestamp
                temp,
                hourly["apparent_temperature"][i],
                hourly["relative_humidity_2m"][i],
                hourly["surface_pressure"][i],
                hourly["wind_speed_10m"][i],
                WEATHER_CODES.get(code, "Unknown"),
                WEATHER_CODES.get(code, "Unknown"),
            )
        )
    return rows


def main():
    end = date.today() - timedelta(days=1)  # archive API needs a completed day
    start = end - timedelta(days=365 * 3)

    conn = psycopg2.connect(**DB_CONFIG)

    with conn.cursor() as cur:
        cur.execute("SELECT city_id FROM dim_city WHERE city_name = %s", (CITY_NAME,))
        row = cur.fetchone()
        if row is None:
            print(f"City '{CITY_NAME}' not found in dim_city -- run create_tables.sql first.")
            sys.exit(1)
        city_id = row[0]

    print(f"Backfilling {CITY_NAME} from {start} to {end}...")

    # Fetch in yearly chunks -- keeps each request a manageable size
    all_rows = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=365), end)
        print(f"  Fetching {chunk_start} -> {chunk_end}")
        data = fetch_historical(chunk_start, chunk_end)
        rows = to_rows(data, city_id)
        all_rows.extend(rows)
        chunk_start = chunk_end + timedelta(days=1)

    print(f"Fetched {len(all_rows)} hourly records. Loading into fact_weather...")

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
            all_rows,
        )
    conn.commit()
    conn.close()
    print("Backfill complete.")


if __name__ == "__main__":
    main()