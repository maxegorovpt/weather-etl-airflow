import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))

from weather.transform import transform_record, transform_all


def make_raw(city="London", temp=15.0, dt=1721840400, missing=None):
    raw_json = {
        "main": {"temp": temp, "feels_like": 14.0, "humidity": 70, "pressure": 1012},
        "wind": {"speed": 5.5},
        "weather": [{"main": "Clouds", "description": "overcast clouds"}],
        "dt": dt,
    }
    if missing:
        # simulate a missing field, e.g. "main.temp" or "dt"
        keys = missing.split(".")
        d = raw_json
        for k in keys[:-1]:
            d = d[k]
        del d[keys[-1]]

    return {
        "city_name": city,
        "country": "GB",
        "fetched_at": "2026-07-24T20:00:00",
        "raw_json": raw_json,
    }


def test_transform_valid_record():
    record = transform_record(make_raw())
    assert record is not None
    assert record["temp_c"] == 15.0
    assert record["weather_main"] == "Clouds"


def test_transform_missing_temp_returns_none():
    record = transform_record(make_raw(missing="main.temp"))
    assert record is None


def test_transform_missing_timestamp_returns_none():
    record = transform_record(make_raw(missing="dt"))
    assert record is None


def test_transform_out_of_range_temp_returns_none():
    record = transform_record(make_raw(temp=999))
    assert record is None


def test_transform_missing_wind_does_not_crash():
    raw = make_raw()
    del raw["raw_json"]["wind"]
    record = transform_record(raw)
    assert record is not None
    assert record["wind_speed"] is None


def test_transform_all_deduplicates():
    raw1 = make_raw(city="London", dt=1721840400)
    raw2 = make_raw(city="London", dt=1721840400)  # exact duplicate
    result = transform_all([raw1, raw2])
    assert len(result) == 1


def test_transform_all_drops_bad_keeps_good():
    good = make_raw(city="London")
    bad = make_raw(city="Nowhere", missing="main.temp")
    result = transform_all([good, bad])
    assert len(result) == 1
    assert result[0]["city_name"] == "London"