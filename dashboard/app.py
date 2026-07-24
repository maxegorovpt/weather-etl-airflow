import os

import pandas as pd
import psycopg2
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Lisbon Weather Dashboard", layout="wide", page_icon="🌤️")

DB_CONFIG = {
    "host": os.getenv("WAREHOUSE_HOST", "weather-db"),
    "port": os.getenv("WAREHOUSE_PORT_INTERNAL", "5432"),
    "dbname": os.getenv("WAREHOUSE_DB", "weather"),
    "user": os.getenv("WAREHOUSE_USER", "weather_user"),
    "password": os.getenv("WAREHOUSE_PASSWORD", "weather_pass"),
}


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    query = """
        SELECT f.observed_at, f.temp_c, f.feels_like_c, f.humidity,
               f.pressure, f.wind_speed, f.weather_main, f.weather_desc
        FROM fact_weather f
        JOIN dim_city c USING(city_id)
        WHERE c.city_name = 'Lisbon'
        ORDER BY f.observed_at
    """
    df = pd.read_sql(query, conn)
    conn.close()
    df["observed_at"] = pd.to_datetime(df["observed_at"])
    df["year"] = df["observed_at"].dt.year
    df["month"] = df["observed_at"].dt.month
    df["hour"] = df["observed_at"].dt.hour
    df["date"] = df["observed_at"].dt.date
    return df


st.title("🌤️ Lisbon Weather Dashboard")
st.caption("3 years of hourly weather data — historical backfill (Open-Meteo) + live hourly updates (Airflow + OpenWeatherMap)")

df = load_data()

if df.empty:
    st.warning("No data yet. Run the backfill script and/or trigger the weather_etl DAG.")
    st.stop()

# ---- Date range filter ----
min_date, max_date = df["date"].min(), df["date"].max()
date_range = st.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
if len(date_range) == 2:
    start_d, end_d = date_range
    df = df[(df["date"] >= start_d) & (df["date"] <= end_d)]

if df.empty:
    st.info("No data in the selected date range.")
    st.stop()

# ---- Top metrics ----
latest = df.sort_values("observed_at").iloc[-1]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Latest temp", f"{latest['temp_c']:.1f}°C", latest["weather_desc"])
col2.metric("Avg temp (period)", f"{df['temp_c'].mean():.1f}°C")
col3.metric("Hottest recorded", f"{df['temp_c'].max():.1f}°C")
col4.metric("Coldest recorded", f"{df['temp_c'].min():.1f}°C")

st.divider()

# ---- Long-term trend (daily average, smoothed) ----
st.subheader("Temperature trend over time")
daily = df.groupby("date")["temp_c"].mean().reset_index()
daily["rolling_7d"] = daily["temp_c"].rolling(7, min_periods=1).mean()
fig_trend = px.line(
    daily, x="date", y=["temp_c", "rolling_7d"],
    labels={"value": "Temp (°C)", "date": "", "variable": ""},
)
fig_trend.data[0].name = "Daily avg"
fig_trend.data[1].name = "7-day rolling avg"
fig_trend.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(fig_trend, use_container_width=True)

# ---- Climatology heatmap: month vs hour ----
st.subheader("Average temperature by month & hour of day")
st.caption("Reveals daily and seasonal rhythm — e.g. summer afternoons vs winter mornings")
heat_data = df.pivot_table(index="hour", columns="month", values="temp_c", aggfunc="mean")
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
heat_data.columns = [month_names[m - 1] for m in heat_data.columns]
fig_heat = px.imshow(
    heat_data,
    labels=dict(x="Month", y="Hour of day", color="Avg °C"),
    color_continuous_scale="RdYlBu_r",
    aspect="auto",
)
st.plotly_chart(fig_heat, use_container_width=True)

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Monthly averages by year")
    monthly = df.groupby(["year", "month"])["temp_c"].mean().reset_index()
    monthly["month_name"] = monthly["month"].apply(lambda m: month_names[m - 1])
    fig_monthly = px.line(
        monthly, x="month_name", y="temp_c", color="year",
        category_orders={"month_name": month_names},
        labels={"temp_c": "Avg Temp (°C)", "month_name": ""},
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

with col_b:
    st.subheader("Weather condition frequency")
    condition_counts = df["weather_main"].value_counts().reset_index()
    condition_counts.columns = ["condition", "count"]
    fig_cond = px.bar(condition_counts, x="condition", y="count")
    st.plotly_chart(fig_cond, use_container_width=True)

# ---- Extremes table ----
st.subheader("Notable extremes in selected period")
hottest_day = df.loc[df["temp_c"].idxmax()]
coldest_day = df.loc[df["temp_c"].idxmin()]
windiest = df.loc[df["wind_speed"].idxmax()]
extremes = pd.DataFrame(
    [
        ["Hottest reading", hottest_day["observed_at"], f"{hottest_day['temp_c']:.1f}°C"],
        ["Coldest reading", coldest_day["observed_at"], f"{coldest_day['temp_c']:.1f}°C"],
        ["Windiest reading", windiest["observed_at"], f"{windiest['wind_speed']:.1f} m/s"],
    ],
    columns=["Metric", "When", "Value"],
)
st.dataframe(extremes, hide_index=True, use_container_width=True)

with st.expander("Raw data"):
    st.dataframe(df.sort_values("observed_at", ascending=False), hide_index=True, use_container_width=True)