# Germany Weather ETL Pipeline

## Project description

An end-to-end ETL pipeline built with **Apache Airflow**, tracking weather
across **Germany's 10 largest cities**. The project combines a one-time,
3-year historical backfill with a live hourly extraction pipeline,
transforms and validates the data, loads it into **PostgreSQL**, and
visualizes it in an interactive **Streamlit** dashboard — including a live
7-day forecast styled after iOS weather widgets.

It was built as a portfolio project to demonstrate practical, production-style
data engineering: idempotent loads, data quality checks, dimensional
modeling, and a pipeline that combines a bulk historical seed with ongoing
incremental updates — the same pattern real data warehouses use.

### Cities tracked

Berlin, Hamburg, Munich, Cologne, Frankfurt, Stuttgart, Dusseldorf, Leipzig,
Dortmund, Essen — Germany's 10 biggest cities by population.

### Architecture

```
Open-Meteo Archive API  ──(one-time backfill, all 10 cities)──┐
                                                                 ├──> Postgres (fact_weather) ──> Streamlit dashboard
OpenWeatherMap API  ──(Airflow, hourly, all 10 cities)─────────┘

Open-Meteo Forecast API ──(live, on-demand)────────────────────────> Streamlit dashboard (Current Weather tab)
```

### Stack

- **Apache Airflow** (TaskFlow API) — orchestration for the ongoing hourly extract
- **PostgreSQL** — data warehouse (star schema: `dim_city` + `fact_weather`)
- **Streamlit + Plotly** — dashboard, including an interactive map (OpenStreetMap tiles)
- **Docker Compose** — local infra for everything above

### Data sources

- **Historical backfill**: [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)
  (free, no key required) — used once to load ~3 years of hourly data per city
- **Live extraction**: [OpenWeatherMap Current Weather API](https://openweathermap.org/current) —
  run hourly by Airflow, across all 10 cities, to keep the dataset current
- **Live forecast**: [Open-Meteo Forecast API](https://open-meteo.com/en/docs/api)
  (free, no key required) — called on-demand by the dashboard's "Current Weather" tab

### Design decisions

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
- Dashboard tables are rendered as plain HTML rather than Streamlit's native
  table widgets, which route through pyarrow's Arrow serialization — a path
  that proved unstable (segfaults) on this platform. Bypassing it trades
  built-in sorting/resizing for a dashboard that doesn't crash

### Dashboard highlights

- Sidebar city list — pick one city, drives the whole dashboard
- **Historical Data tab**: country header, interactive map (bubble size =
  population, color = avg temperature), city comparison bar charts, weather
  condition mix, wind speed distribution, summary table, and a per-city deep
  dive (temperature trend with rolling average, monthly distribution box plot)
- **Current Weather tab**: live current conditions and 7-day forecast styled
  after iOS weather widgets — big current temp, hourly mini chart, a row of
  day cards, and a high/low trend line

## Getting started from scratch

### Prerequisites

- Docker Desktop installed and running
- Python 3 (for running the one-time backfill script from your host machine)
- A free [OpenWeatherMap API key](https://openweathermap.org/api) (sign up,
  key may take up to ~1 hour to activate after signup)

### 1. Clone and configure environment variables

```bash
git clone <your-repo-url>
cd weather-etl-airflow
```

Create `.env` in the project root:

```
AIRFLOW_UID=50000

_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow

WAREHOUSE_DB=weather
WAREHOUSE_USER=weather_user
WAREHOUSE_PASSWORD=weather_pass
WAREHOUSE_PORT=5433

OWM_API_KEY=your_openweathermap_api_key_here
```

On Linux, replace `AIRFLOW_UID=50000` with your actual UID (`id -u`) to avoid
volume permission issues.

### 2. Build and start all services

```bash
docker-compose build
docker-compose up airflow-init
docker-compose up -d
```

Give it 1–2 minutes on first boot. Check everything is healthy:

```bash
docker-compose ps
```

You should see `airflow-webserver`, `airflow-scheduler`, `airflow-triggerer`,
`postgres`, `redis`, `weather-db`, and `dashboard` all `Up`.

### 3. Create the database schema

```bash
docker cp sql/create_tables.sql weather_warehouse:/create_tables.sql
docker exec -it weather_warehouse psql -U weather_user -d weather -f /create_tables.sql
```

Verify the 10 cities were seeded:

```bash
docker exec -it weather_warehouse psql -U weather_user -d weather -c \
  "SELECT city_name, population FROM dim_city ORDER BY population DESC;"
```

### 4. Configure Airflow

Open [localhost:8080](http://localhost:8080), log in with `airflow` / `airflow`.

**Add the API key as a Variable:**
Admin → Variables → + → Key: `owm_api_key`, Value: your OpenWeatherMap key

**Add the Postgres connection:**
Admin → Connections → +

| Field | Value |
|---|---|
| Connection Id | `weather_warehouse` |
| Connection Type | `Postgres` |
| Host | `weather-db` |
| Database | `weather` |
| Login | `weather_user` |
| Password | `weather_pass` |
| Port | `5432` |

### 5. Run the one-time historical backfill

From your host machine (not inside Docker):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests psycopg2-binary
python3 scripts/backfill_cities.py
```

This pulls ~3 years of hourly data for all 10 cities from Open-Meteo — takes
a few minutes. Verify it landed:

```bash
docker exec -it weather_warehouse psql -U weather_user -d weather -c \
  "SELECT MIN(observed_at), MAX(observed_at), COUNT(*) FROM fact_weather;"
```

### 6. Start the live hourly pipeline

In the Airflow UI, find `weather_etl` in the DAG list, unpause it, and
trigger a manual run to confirm it works. Going forward it runs automatically
every hour, adding live data on top of the historical backfill.

### 7. View the dashboard

Open [localhost:8501](http://localhost:8501). Pick a city from the sidebar
list, and switch between the **Historical Data** and **Current Weather** tabs.

## Access

| Service | URL |
|---|---|
| Airflow UI | [localhost:8080](http://localhost:8080) |
| Dashboard | [localhost:8501](http://localhost:8501) |
| Postgres (host access) | `localhost:5433` |

## Screenshots
[DAG graph view] 
<img width="1423" height="848" alt="Screenshot 2026-07-25 at 11 43 02" src="https://github.com/user-attachments/assets/ab359f7d-e5e0-4b99-87b1-b96c0d78ebbe" />

[dashboard]
<img width="1429" height="616" alt="Screenshot 2026-07-25 at 11 43 52" src="https://github.com/user-attachments/assets/4e7d26db-162e-48fc-89fa-375447c8a887" />
<img width="1383" height="530" alt="Screenshot 2026-07-25 at 11 44 37" src="https://github.com/user-attachments/assets/72842c6d-6cdc-4301-96ca-d09ebfce8f6b" />
<img width="1368" height="487" alt="3" src="https://github.com/user-attachments/assets/f54527a6-c271-4175-a78a-d0f543de8dd6" />
<img width="1390" height="509" alt="4" src="https://github.com/user-attachments/assets/3e2fbc21-e133-462c-b418-f3beafdd625f" />
<img width="1377" height="464" alt="5" src="https://github.com/user-attachments/assets/8a18fff5-4d7d-4020-9964-c700de857203" />
<img width="1372" height="503" alt="6" src="https://github.com/user-attachments/assets/22b4e802-1303-4f88-952c-46e727c88714" />
<img width="1376" height="494" alt="7" src="https://github.com/user-attachments/assets/1f06deab-e90e-4fc7-881b-cc9a9f6481d1" />
<img width="1351" height="477" alt="8" src="https://github.com/user-attachments/assets/561d04c8-b28b-4d75-8d13-dd1c5c89846b" />
<img width="1353" height="628" alt="9" src="https://github.com/user-attachments/assets/8dae1f1d-a4e1-42b9-bd36-5c6ba1287c97" />



