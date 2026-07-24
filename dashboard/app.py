import os

import pandas as pd
import psycopg2
import streamlit as st

st.set_page_config(page_title="Weather ETL Dashboard", layout="wide")

DB_CONFIG = {
    "host": os.getenv("WAREHOUSE_HOST", "weather-db"),
    "port": os.getenv("WAREHOUSE_PORT_INTERNAL", "5432"),
    "dbname": os.getenv("WAREHOUSE_DB", "weather"),
    "user": os.getenv("WAREHOUSE_USER", "weather_user"),
    "password": os.getenv("WAREHOUSE_PASSWORD", "weather_pass"),
}


@st.cache_data(ttl=300)  # cache 5 min so we're not hammering the DB on every interaction
def load_data() -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    query = """
        SELECT c.city_name, c.country, f.observed_at, f.temp_c,
               f.feels_like_c, f.humidity, f.pressure, f.wind_speed,
               f.weather_main, f.weather_desc
        FROM fact_weather f
        JOIN dim_city c USING(city_id)
        ORDER BY f.observed_at
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


st.title("🌤️ Weather ETL Dashboard")
st.caption("Data extracted hourly from OpenWeatherMap via an Airflow pipeline")

df = load_data()

if df.empty:
    st.warning("No data yet -- trigger the weather_etl DAG in Airflow first.")
    st.stop()

cities = sorted(df["city_name"].unique())
selected_cities = st.multiselect("Cities", cities, default=cities)

filtered = df[df["city_name"].isin(selected_cities)]

col1, col2, col3 = st.columns(3)
col1.metric("Cities tracked", len(cities))
col2.metric("Observations", len(filtered))
col3.metric("Latest reading", filtered["observed_at"].max().strftime("%Y-%m-%d %H:%M UTC"))

st.subheader("Temperature over time")
temp_pivot = filtered.pivot_table(index="observed_at", columns="city_name", values="temp_c")
st.line_chart(temp_pivot)

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Average humidity by city")
    humidity_avg = filtered.groupby("city_name")["humidity"].mean().sort_values(ascending=False)
    st.bar_chart(humidity_avg)

with col_b:
    st.subheader("Latest conditions")
    latest = (
        filtered.sort_values("observed_at")
        .groupby("city_name")
        .last()
        .reset_index()[["city_name", "temp_c", "weather_desc", "wind_speed"]]
    )
    st.dataframe(latest, hide_index=True, use_container_width=True)

st.subheader("Raw observations")
st.dataframe(
    filtered.sort_values("observed_at", ascending=False),
    hide_index=True,
    use_container_width=True,
)