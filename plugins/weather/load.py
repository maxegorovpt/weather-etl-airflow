"""
Load: write raw JSON to raw_weather (audit trail) and upsert clean records
into fact_weather. Uses ON CONFLICT to make loads idempotent -- safe to
re-run without creating duplicates.
"""
import logging

from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


def load_raw(conn, raw_records: list[dict]) -> None:
    """Insert raw API responses into raw_weather for audit/replay purposes."""
    import json

    with conn.cursor() as cur:
        rows = [
            (r["city_name"], r["fetched_at"], json.dumps(r["raw_json"]))
            for r in raw_records
        ]
        execute_values(
            cur,
            """
            INSERT INTO raw_weather (city_name, fetched_at, raw_json)
            VALUES %s
            """,
            rows,
            template="(%s, %s, %s::jsonb)",
        )
    conn.commit()
    logger.info(f"Loaded {len(raw_records)} rows into raw_weather")


def _get_city_id_map(conn) -> dict[str, int]:
    """Fetch city_name -> city_id mapping from dim_city."""
    with conn.cursor() as cur:
        cur.execute("SELECT city_id, city_name FROM dim_city")
        return {name: city_id for city_id, name in cur.fetchall()}


def load_fact(conn, clean_records: list[dict]) -> int:
    """
    Upsert clean records into fact_weather.
    Returns the number of rows affected.
    Records for cities not found in dim_city are skipped and logged.
    """
    city_id_map = _get_city_id_map(conn)

    rows = []
    for r in clean_records:
        city_id = city_id_map.get(r["city_name"])
        if city_id is None:
            logger.warning(
                f"Skipping record for unknown city '{r['city_name']}' "
                f"(not in dim_city -- add it there first)"
            )
            continue
        rows.append(
            (
                city_id,
                r["observed_at"],
                r["temp_c"],
                r["feels_like_c"],
                r["humidity"],
                r["pressure"],
                r["wind_speed"],
                r["weather_main"],
                r["weather_desc"],
            )
        )

    if not rows:
        raise RuntimeError("No valid rows to load -- all cities unknown or filtered out.")

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO fact_weather
                (city_id, observed_at, temp_c, feels_like_c, humidity,
                 pressure, wind_speed, weather_main, weather_desc)
            VALUES %s
            ON CONFLICT (city_id, observed_at)
            DO UPDATE SET
                temp_c = EXCLUDED.temp_c,
                feels_like_c = EXCLUDED.feels_like_c,
                humidity = EXCLUDED.humidity,
                pressure = EXCLUDED.pressure,
                wind_speed = EXCLUDED.wind_speed,
                weather_main = EXCLUDED.weather_main,
                weather_desc = EXCLUDED.weather_desc,
                loaded_at = now()
            """,
            rows,
        )
    conn.commit()
    logger.info(f"Upserted {len(rows)} rows into fact_weather")
    return len(rows)