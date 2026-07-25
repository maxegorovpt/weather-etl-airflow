-- Dimension: cities we track
CREATE TABLE IF NOT EXISTS dim_city (
    city_id SERIAL PRIMARY KEY,
    city_name TEXT NOT NULL,
    country TEXT,
    lat FLOAT,
    lon FLOAT,
    population INT,
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

-- Seed: Germany's 10 biggest cities by population (approx, 2024 figures)
INSERT INTO dim_city (city_name, country, lat, lon, population) VALUES
    ('Berlin', 'DE', 52.5200, 13.4050, 3677000),
    ('Hamburg', 'DE', 53.5511, 9.9937, 1906000),
    ('Munich', 'DE', 48.1351, 11.5820, 1512000),
    ('Cologne', 'DE', 50.9375, 6.9603, 1073000),
    ('Frankfurt', 'DE', 50.1109, 8.6821, 773000),
    ('Stuttgart', 'DE', 48.7758, 9.1829, 626000),
    ('Dusseldorf', 'DE', 51.2277, 6.7735, 620000),
    ('Leipzig', 'DE', 51.3397, 12.3731, 601000),
    ('Dortmund', 'DE', 51.5136, 7.4653, 588000),
    ('Essen', 'DE', 51.4556, 7.0116, 579000)
ON CONFLICT (city_name, country) DO UPDATE SET
    lat = EXCLUDED.lat, lon = EXCLUDED.lon, population = EXCLUDED.population;