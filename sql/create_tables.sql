-- Dimension: cities we track
CREATE TABLE IF NOT EXISTS dim_city (
    city_id SERIAL PRIMARY KEY,
    city_name TEXT NOT NULL,
    country TEXT,
    lat FLOAT,
    lon FLOAT,
    UNIQUE(city_name, country)
);

-- Raw landing zone: full API responses, untouched
CREATE TABLE IF NOT EXISTS raw_weather (
    id SERIAL PRIMARY KEY,
    city_name TEXT NOT NULL,
    fetched_at TIMESTAMP NOT NULL DEFAULT now(),
    raw_json JSONB NOT NULL
);

-- Fact table: clean, structured, one row per city per observation time
CREATE TABLE IF NOT EXISTS fact_weather (
    id SERIAL PRIMARY KEY,
    city_id INT NOT NULL REFERENCES dim_city(city_id),
    observed_at TIMESTAMP NOT NULL,
    temp_c FLOAT,
    feels_like_c FLOAT,
    humidity INT,
    pressure INT,
    wind_speed FLOAT,
    weather_main TEXT,
    weather_desc TEXT,
    loaded_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE(city_id, observed_at)
);

-- Seed the cities we'll track
INSERT INTO dim_city (city_name, country, lat, lon) VALUES
    ('London', 'GB', 51.5074, -0.1278),
    ('New York', 'US', 40.7128, -74.0060),
    ('Tokyo', 'JP', 35.6895, 139.6917),
    ('Sydney', 'AU', -33.8688, 151.2093),
    ('Cape Town', 'ZA', -33.9249, 18.4241),
    ('Lisbon', 'PT', 38.7223, -9.1393)
ON CONFLICT (city_name, country) DO NOTHING;