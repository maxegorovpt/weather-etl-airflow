# Lisbon Weather ETL Pipeline

An end-to-end ETL pipeline built with Airflow, combining a 3-year historical
backfill with live hourly extraction, transforming and validating the data,
and loading it into Postgres — visualized in an interactive Streamlit
dashboard.

## Architecture
[diagram here]

```
Open-Meteo Archive API  ──(one-time backfill)──┐
                                                 ├──> Postgres (fact_weather) ──> Streamlit dashboard
OpenWeatherMap API  ──(Airflow, hourly)────────┘
```

## Stack
- Apache Airflow (TaskFlow API) — orchestration for the ongoing hourly extract
- PostgreSQL — data warehouse (star schema: `dim_city` + `fact_weather`)
- Streamlit + Plotly — dashboard
- Docker Compose — local infra

## Data sources
- **Historical backfill**: [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)
  (free, no key required) — used once to load ~3 years of hourly data for Lisbon
- **Live extraction**: [OpenWeatherMap Current Weather API](https://openweathermap.org/current) —
  run hourly by Airflow to keep the dataset current going forward

Combining a bulk historical load with an incremental live pipeline mirrors how
real-world data warehouses are seeded (backfill) and then kept up to date
(incremental ETL).

## Design decisions
- Idempotent upserts (`ON CONFLICT`) so retries/backfills never duplicate data
- Raw landing table (`raw_weather`) preserves API responses for replay
- Data quality task validates row counts, nulls, and sane value ranges
- One-time historical backfill (Open-Meteo) seeds 3 years of data; Airflow
  DAG extracts hourly going forward — same target schema for both

## Dashboard highlights
- Long-term temperature trend with 7-day rolling average
- Climatology heatmap: average temperature by month × hour of day
- Year-over-year monthly comparison
- Weather condition frequency breakdown
- Notable extremes (hottest/coldest/windiest readings) over the selected period

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
4. Run the one-time historical backfill from your host machine:
   ```bash
   python3 scripts/backfill_lisbon.py
   ```
5. Unpause and trigger the `weather_etl` DAG to start hourly live updates
6. View the [dashboard](http://localhost:8501)

## Screenshots
[DAG graph view] 
<img width="930" height="851" alt="Screenshot 2026-07-25 at 00 18 25" src="https://github.com/user-attachments/assets/275ba3bb-7e17-4a70-956b-8d39e5c90303" />

[dashboard]
<img width="1325" height="821" alt="Screenshot 2026-07-25 at 00 07 24" src="https://github.com/user-attachments/assets/c56af2bf-551c-48c1-879c-c36db539e9bd" />
<img width="1310" height="506" alt="Screenshot 2026-07-25 at 00 07 42" src="https://github.com/user-attachments/assets/3ff1a527-7a93-435d-8016-a28c13ed70e8" />
<img width="1307" height="537" alt="Screenshot 2026-07-25 at 00 17 00" src="https://github.com/user-attachments/assets/663bc96d-ec86-4fd7-ba21-d4d03797b55c" />
<img width="1326" height="478" alt="Screenshot 2026-07-25 at 00 07 59" src="https://github.com/user-attachments/assets/e2d1d789-8ae4-4838-b128-626494911298" />

