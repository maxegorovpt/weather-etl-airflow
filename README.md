# Weather ETL Pipeline

An end-to-end ETL pipeline built with Airflow, extracting hourly weather
data from OpenWeatherMap, transforming and validating it, and loading it
into Postgres — visualized in a Streamlit dashboard.

## Architecture
[diagram here]

## Stack
- Apache Airflow (TaskFlow API) — orchestration
- PostgreSQL — data warehouse (star schema: dim_city + fact_weather)
- Streamlit — dashboard
- Docker Compose — local infra

## Design decisions
- Idempotent upserts (ON CONFLICT) so retries/backfills never duplicate data
- Raw landing table (raw_weather) preserves API responses for replay
- Data quality task validates row counts, nulls, and sane value ranges
- Per-city extract failures don't abort the whole run

## Setup
1. Copy `.env.example` to `.env`, add your OpenWeatherMap API key
2. `docker-compose up -d`
3. In Airflow UI (localhost:8080), add the `owm_api_key` Variable and
   `weather_warehouse` Postgres connection
4. Unpause and trigger the `weather_etl` DAG
5. View dashboard at localhost:8501

## Screenshots
[DAG graph view] [dashboard]