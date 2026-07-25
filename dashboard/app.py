import os

import pandas as pd
import psycopg2
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Germany Weather Dashboard", layout="wide", page_icon="🇩🇪")

DB_CONFIG = {
    "host": os.getenv("WAREHOUSE_HOST", "weather-db"),
    "port": os.getenv("WAREHOUSE_PORT_INTERNAL", "5432"),
    "dbname": os.getenv("WAREHOUSE_DB", "weather"),
    "user": os.getenv("WAREHOUSE_USER", "weather_user"),
    "password": os.getenv("WAREHOUSE_PASSWORD", "weather_pass"),
}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    query = """
        SELECT c.city_name, c.population, c.lat, c.lon, f.observed_at, f.temp_c,
               f.feels_like_c, f.humidity, f.pressure, f.wind_speed,
               f.weather_main, f.weather_desc
        FROM fact_weather f
        JOIN dim_city c USING(city_id)
        WHERE c.country = 'DE'
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


# ---------------- Header: country info ----------------
st.title("🇩🇪 Germany Weather Dashboard")
st.caption("Hourly weather across Germany's 10 largest cities — historical backfill (Open-Meteo) + live hourly updates (Airflow + OpenWeatherMap)")

st.markdown(
    "Germany sits in Central Europe with a temperate seasonal climate — "
    "warm summers, cool winters, and rain distributed fairly evenly year-round. "
    "This dashboard tracks weather across the country's 10 largest cities, "
    "from coastal Hamburg to alpine-adjacent Munich."
)

col_info1, col_info2, col_info3, col_info4, col_info5 = st.columns(5)
col_info1.metric("Capital", "Berlin")
col_info2.metric("Population", "~84.5M")
col_info3.metric("Currency", "Euro (€)")
col_info4.metric("Time zone", "CET/CEST")
col_info5.metric("Cities tracked", "10")

st.divider()

df = load_data()

if df.empty:
    st.warning("No data yet. Run the backfill script and/or trigger the weather_etl DAG.")
    st.stop()

# ---------------- Filters ----------------
all_cities = sorted(df["city_name"].unique())
selected_cities = st.multiselect("Cities", all_cities, default=all_cities)

min_date, max_date = df["date"].min(), df["date"].max()
date_range = st.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)

if not selected_cities:
    st.info("Select at least one city to see data.")
    st.stop()

df = df[df["city_name"].isin(selected_cities)]

if len(date_range) == 2:
    start_d, end_d = date_range
    df = df[(df["date"] >= start_d) & (df["date"] <= end_d)]

if df.empty:
    st.info("No data for this selection.")
    st.stop()

# ---------------- Top metrics (averaged across selected cities) ----------------
latest_per_city = df.sort_values("observed_at").groupby("city_name").last()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Avg temp (selected)", f"{df['temp_c'].mean():.1f}°C")
col2.metric("Avg humidity (selected)", f"{df['humidity'].mean():.0f}%")
col3.metric("Hottest recorded", f"{df['temp_c'].max():.1f}°C")
col4.metric("Coldest recorded", f"{df['temp_c'].min():.1f}°C")

st.divider()

# ---------------- Map: cities with population + avg temp ----------------
st.subheader("Cities at a glance")
st.caption("Bubble size = population · color = average temperature (selected period)")
map_data = df.groupby("city_name").agg(
    lat=("lat", "first"),
    lon=("lon", "first"),
    population=("population", "first"),
    avg_temp=("temp_c", "mean"),
    avg_humidity=("humidity", "mean"),
).reset_index()

fig_map = px.scatter_mapbox(
    map_data,
    lat="lat", lon="lon",
    size="population",
    color="avg_temp",
    color_continuous_scale="RdYlBu_r",
    hover_name="city_name",
    hover_data={"population": True, "avg_temp": ":.1f", "avg_humidity": ":.0f", "lat": False, "lon": False},
    size_max=45,
    zoom=4.7,
    center={"lat": 51.1657, "lon": 10.4515},
    labels={"avg_temp": "Avg Temp (°C)", "population": "Population"},
)
fig_map.update_layout(
    mapbox_style="open-street-map",
    height=500,
    margin=dict(l=0, r=0, t=0, b=0),
)
st.plotly_chart(fig_map, use_container_width=True)

st.divider()

# ---------------- Temperature trend, one line per city ----------------
st.subheader("Temperature trend over time")
daily = df.groupby(["date", "city_name"])["temp_c"].mean().reset_index()
fig_trend = px.line(
    daily, x="date", y="temp_c", color="city_name",
    labels={"temp_c": "Temp (°C)", "date": "", "city_name": "City"},
)
st.plotly_chart(fig_trend, use_container_width=True)

# ---------------- City comparison bar: avg temp ----------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Average temperature by city")
    avg_temp = df.groupby("city_name")["temp_c"].mean().sort_values(ascending=False).reset_index()
    fig_avg_temp = px.bar(
        avg_temp, x="city_name", y="temp_c", color="temp_c",
        color_continuous_scale="OrRd", text_auto=".1f",
        labels={"temp_c": "Avg Temp (°C)", "city_name": ""},
    )
    fig_avg_temp.update_layout(showlegend=False, coloraxis_showscale=False)
    fig_avg_temp.update_traces(textposition="outside")
    st.plotly_chart(fig_avg_temp, use_container_width=True)

with col_b:
    st.subheader("Average humidity by city")
    avg_humidity = df.groupby("city_name")["humidity"].mean().sort_values(ascending=False).reset_index()
    fig_avg_humidity = px.bar(
        avg_humidity, x="city_name", y="humidity", color="humidity",
        color_continuous_scale="Blues", text_auto=".0f",
        labels={"humidity": "Avg Humidity (%)", "city_name": ""},
    )
    fig_avg_humidity.update_layout(showlegend=False, coloraxis_showscale=False)
    fig_avg_humidity.update_traces(textposition="outside")
    st.plotly_chart(fig_avg_humidity, use_container_width=True)

# ---------------- Climatology heatmap ----------------
st.subheader("Average temperature by month & hour of day")
st.caption("Daily & seasonal rhythm — pick one city for a detailed view, or compare several side by side")

heatmap_city_choice = st.selectbox(
    "City for this chart", ["Compare selected cities"] + selected_cities
)

if heatmap_city_choice == "Compare selected cities":
    # Small multiples: one compact heatmap per city, side by side
    n = len(selected_cities)
    cols = st.columns(min(n, 3))
    for i, city in enumerate(selected_cities):
        city_df = df[df["city_name"] == city]
        heat_data = city_df.pivot_table(index="hour", columns="month", values="temp_c", aggfunc="mean")
        heat_data.columns = [MONTH_NAMES[m - 1] for m in heat_data.columns]
        fig = px.imshow(
            heat_data, color_continuous_scale="RdYlBu_r", aspect="auto",
            labels=dict(x="", y="Hour", color="°C"),
        )
        fig.update_layout(title=city, height=280, coloraxis_showscale=False, margin=dict(t=40, b=20))
        cols[i % 3].plotly_chart(fig, use_container_width=True)
else:
    city_df = df[df["city_name"] == heatmap_city_choice]
    heat_data = city_df.pivot_table(index="hour", columns="month", values="temp_c", aggfunc="mean")
    heat_data.columns = [MONTH_NAMES[m - 1] for m in heat_data.columns]
    fig_heat = px.imshow(
        heat_data,
        labels=dict(x="Month", y="Hour of day", color="Avg °C"),
        color_continuous_scale="RdYlBu_r",
        aspect="auto",
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# ---------------- Weather condition frequency ----------------
st.subheader("Weather condition mix by city")
st.caption("Share of time spent in each condition — normalized so cities are comparable regardless of data volume")
condition_counts = df.groupby(["city_name", "weather_main"]).size().reset_index(name="count")
condition_counts["pct"] = condition_counts.groupby("city_name")["count"].transform(lambda x: x / x.sum() * 100)
fig_cond = px.bar(
    condition_counts, x="city_name", y="pct", color="weather_main",
    barmode="stack",
    labels={"city_name": "", "pct": "Share of readings (%)", "weather_main": "Condition"},
)
st.plotly_chart(fig_cond, use_container_width=True)

# ---------------- Wind speed distribution ----------------
st.subheader("Wind speed distribution")
fig_wind = px.histogram(
    df, x="wind_speed", color="city_name", nbins=30, opacity=0.7,
    labels={"wind_speed": "Wind speed (m/s)", "city_name": "City"},
)
st.plotly_chart(fig_wind, use_container_width=True)

# ---------------- City summary table ----------------
st.subheader("City summary")
summary = df.groupby("city_name").agg(
    population=("population", "first"),
    avg_temp_c=("temp_c", "mean"),
    max_temp_c=("temp_c", "max"),
    min_temp_c=("temp_c", "min"),
    avg_humidity=("humidity", "mean"),
    avg_wind_speed=("wind_speed", "mean"),
).round(1).reset_index()
summary.columns = ["City", "Population", "Avg Temp (°C)", "Max Temp (°C)",
                    "Min Temp (°C)", "Avg Humidity (%)", "Avg Wind (m/s)"]
summary = summary.sort_values("Population", ascending=False)
st.dataframe(summary, hide_index=True, use_container_width=True)

with st.expander("Raw data"):
    st.dataframe(df.sort_values("observed_at", ascending=False), hide_index=True, use_container_width=True)