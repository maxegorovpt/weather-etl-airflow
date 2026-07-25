# Germany Weather ETL Pipeline

An end-to-end ETL pipeline built with Airflow, tracking weather across
**Germany's 10 largest cities**. Combines a 3-year historical backfill with
live hourly extraction, transforms and validates the data, loads it into
Postgres, and visualizes it in an interactive Streamlit dashboard with
city-level filtering and comparison.

## Cities tracked

Berlin, Hamburg, Munich, Cologne, Frankfurt, Stuttgart, Dusseldorf, Leipzig,
Dortmund, Essen — Germany's 10 biggest cities by population.

## Architecture
[diagram here]

```
Open-Meteo Archive API  ──(one-time backfill, all 10 cities)──┐
                                                                 ├──> Postgres (fact_weather) ──> Streamlit dashboard
OpenWeatherMap API  ──(Airflow, hourly, all 10 cities)─────────┘
```

## Stack
- Apache Airflow (TaskFlow API) — orchestration for the ongoing hourly extract
- PostgreSQL — data warehouse (star schema: `dim_city` + `fact_weather`)
- Streamlit + Plotly — dashboard, including an interactive map (OpenStreetMap tiles)
- Docker Compose — local infra

## Data sources
- **Historical backfill**: [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)
  (free, no key required) — used once to load ~3 years of hourly data per city
- **Live extraction**: [OpenWeatherMap Current Weather API](https://openweathermap.org/current) —
  run hourly by Airflow, across all 10 cities, to keep the dataset current

Combining a bulk historical load with an incremental live pipeline mirrors how
real-world data warehouses are seeded (backfill) and then kept up to date
(incremental ETL).

## Design decisions
- Idempotent upserts (`ON CONFLICT`) so retries/backfills never duplicate data
- Raw landing table (`raw_weather`) preserves API responses for replay
- Data quality task validates row counts, nulls, and sane value ranges
- One-time historical backfill (Open-Meteo) seeds 3 years of data per city;
  Airflow DAG extracts hourly going forward — same target schema for both
- `dim_city` carries population and coordinates, enabling comparisons beyond
  raw weather (e.g. population-weighted metrics, the city map)
- Backfill script reads its city list dynamically from `dim_city` rather than
  a hardcoded list, so adding/removing tracked cities requires no code change
- Weather condition mix is normalized to percentages per city (not raw counts),
  so cities with different amounts of data remain fairly comparable

## Dashboard highlights
- Country-level header: capital, population, currency, time zone, cities tracked
- Interactive map: city bubbles sized by population, colored by average
  temperature, with humidity on hover
- Multi-select city filter + date range (compare one, several, or all 10 cities)
- Temperature trend, one line per selected city
- City comparison bar charts: average temperature and humidity, color-scaled
- Climatology view: per-city small-multiple heatmaps (month × hour of day),
  or a detailed single-city view via dropdown
- Weather condition mix by city, shown as normalized percentages
- Wind speed distribution, overlaid by city
- City summary table (population + key weather stats, sorted by population)

## Access

| Service | URL |
|---|---|
| Airflow UI | [localhost:8080](http://localhost:8080) |
| Dashboard | [localhost:8501](http://localhost:8501) |
| Postgres (host access) | `localhost:5433` |

## Setup

1. Copy `.env.example` to `.env`, add your OpenWeatherMap API key
2. `docker-compose up -d`
3. In [Airflow UI](http://localhost:8080), add the `owm_api_key` Variable and
   `weather_warehouse` Postgres connection
4. Run the one-time historical backfill (all 10 cities) from your host machine:
   ```bash
   python3 scripts/backfill_cities.py
   ```
5. Unpause and trigger the `weather_etl` DAG to start hourly live updates
6. View the [dashboard](http://localhost:8501)

## Screenshots
[DAG graph view] [dashboard]