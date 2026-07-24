"""
Weather ETL DAG.
Extracts current weather for tracked cities from OpenWeatherMap,
transforms and validates it, loads it into Postgres, then runs
a data quality check on the loaded data.
"""
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook

from weather.extract import extract_all
from weather.transform import transform_all
from weather.load import load_raw, load_fact

default_args = {
    "owner": "airflow",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="weather_etl",
    description="Extract weather data, transform, load into Postgres",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["weather", "etl", "portfolio"],
)
def weather_etl():
    @task
    def extract():
        api_key = Variable.get("owm_api_key")
        return extract_all(api_key)

    @task
    def transform(raw_records: list[dict]):
        return transform_all(raw_records)

    @task
    def load(raw_records: list[dict], clean_records: list[dict]):
        hook = PostgresHook(postgres_conn_id="weather_warehouse")
        conn = hook.get_conn()
        try:
            load_raw(conn, raw_records)
            rows_loaded = load_fact(conn, clean_records)
        finally:
            conn.close()
        return rows_loaded

    @task
    def data_quality_check(rows_loaded: int):
        hook = PostgresHook(postgres_conn_id="weather_warehouse")
        conn = hook.get_conn()
        try:
            with conn.cursor() as cur:
                # 1. Confirm we actually loaded something this run
                if rows_loaded == 0:
                    raise ValueError("Data quality check failed: 0 rows loaded")

                # 2. No nulls in required fields for recent data
                cur.execute(
                    """
                    SELECT COUNT(*) FROM fact_weather
                    WHERE loaded_at > now() - interval '1 hour'
                    AND (temp_c IS NULL OR city_id IS NULL OR observed_at IS NULL)
                    """
                )
                null_count = cur.fetchone()[0]
                if null_count > 0:
                    raise ValueError(
                        f"Data quality check failed: {null_count} rows with null required fields"
                    )

                # 3. Sanity range check on temps loaded this run
                cur.execute(
                    """
                    SELECT COUNT(*) FROM fact_weather
                    WHERE loaded_at > now() - interval '1 hour'
                    AND (temp_c < -90 OR temp_c > 60)
                    """
                )
                out_of_range = cur.fetchone()[0]
                if out_of_range > 0:
                    raise ValueError(
                        f"Data quality check failed: {out_of_range} rows with out-of-range temps"
                    )
        finally:
            conn.close()

        print(f"Data quality check passed. {rows_loaded} rows loaded this run.")

    raw = extract()
    clean = transform(raw)
    rows_loaded = load(raw, clean)
    data_quality_check(rows_loaded)


weather_etl()