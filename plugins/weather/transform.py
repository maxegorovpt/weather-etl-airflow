"""
Transform: convert raw OpenWeatherMap JSON into clean, flat records
ready to load into fact_weather.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Sanity bounds -- anything outside this is almost certainly bad data
MIN_TEMP_C = -90
MAX_TEMP_C = 60


def _safe_get(d: dict, *keys, default=None):
    """Walk nested dict keys safely, returning default if any level is missing."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def transform_record(raw_record: dict) -> dict | None:
    """
    Transform one raw_weather-style record (city_name, country, fetched_at, raw_json)
    into a flat dict ready for fact_weather.
    Returns None if the record is unusable (missing required fields).
    """
    raw = raw_record["raw_json"]

    temp_c = _safe_get(raw, "main", "temp")
    observed_at_unix = raw.get("dt")

    if temp_c is None or observed_at_unix is None:
        logger.warning(
            f"Skipping record for {raw_record['city_name']}: missing temp or timestamp"
        )
        return None

    if not (MIN_TEMP_C <= temp_c <= MAX_TEMP_C):
        logger.warning(
            f"Skipping record for {raw_record['city_name']}: "
            f"temp {temp_c} out of sane range"
        )
        return None

    weather_list = raw.get("weather", [])
    weather_main = weather_list[0].get("main") if weather_list else None
    weather_desc = weather_list[0].get("description") if weather_list else None

    return {
        "city_name": raw_record["city_name"],
        "country": raw_record["country"],
        "observed_at": datetime.fromtimestamp(observed_at_unix, tz=timezone.utc),
        "temp_c": temp_c,
        "feels_like_c": _safe_get(raw, "main", "feels_like"),
        "humidity": _safe_get(raw, "main", "humidity"),
        "pressure": _safe_get(raw, "main", "pressure"),
        "wind_speed": _safe_get(raw, "wind", "speed"),
        "weather_main": weather_main,
        "weather_desc": weather_desc,
    }


def transform_all(raw_records: list[dict]) -> list[dict]:
    """
    Transform a list of raw records, dropping any that fail validation.
    Also deduplicates on (city_name, observed_at) in case of overlapping runs.
    """
    transformed = []
    seen = set()

    for raw_record in raw_records:
        clean = transform_record(raw_record)
        if clean is None:
            continue

        key = (clean["city_name"], clean["observed_at"])
        if key in seen:
            logger.info(f"Dropping duplicate record: {key}")
            continue
        seen.add(key)
        transformed.append(clean)

    if not transformed:
        raise RuntimeError("Transform produced zero valid records -- aborting DAG run.")

    return transformed