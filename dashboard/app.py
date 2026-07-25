import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Germany Weather Dashboard", layout="wide", page_icon="🇩🇪")

DB_URL = (
    f"postgresql+psycopg2://"
    f"{os.getenv('WAREHOUSE_USER', 'weather_user')}:"
    f"{os.getenv('WAREHOUSE_PASSWORD', 'weather_pass')}@"
    f"{os.getenv('WAREHOUSE_HOST', 'weather-db')}:"
    f"{os.getenv('WAREHOUSE_PORT_INTERNAL', '5432')}/"
    f"{os.getenv('WAREHOUSE_DB', 'weather')}"
)

# One shared engine, connection-pooled -- created once per process, not per rerun
@st.cache_resource
def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

WEATHER_EMOJI = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️", 56: "🌧️", 57: "🌧️",
    61: "🌧️", 63: "🌧️", 65: "🌧️", 66: "🌧️", 67: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "❄️", 77: "🌨️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    85: "🌨️", 86: "❄️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}
WEATHER_LABEL = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Violent showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Severe thunderstorm",
}


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    engine = get_engine()
    query = """
        SELECT c.city_name, c.population, c.lat, c.lon, f.observed_at, f.temp_c,
               f.feels_like_c, f.humidity, f.pressure, f.wind_speed,
               f.weather_main, f.weather_desc
        FROM fact_weather f
        JOIN dim_city c USING(city_id)
        WHERE c.country = 'DE'
        ORDER BY f.observed_at
    """
    df = pd.read_sql(query, engine)
    df["observed_at"] = pd.to_datetime(df["observed_at"])
    df["year"] = df["observed_at"].dt.year
    df["month"] = df["observed_at"].dt.month
    df["hour"] = df["observed_at"].dt.hour
    df["date"] = df["observed_at"].dt.date
    return df


@st.cache_data(ttl=900)  # refresh every 15 min
def fetch_forecast(lat: float, lon: float) -> dict:
    """Live current + 7-day forecast from Open-Meteo (free, no API key)."""
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "hourly": "temperature_2m,weathercode",
            "daily": "temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum",
            "timezone": "auto",
            "forecast_days": 7,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------- Header ----------------
st.title("🇩🇪 Germany Weather Dashboard")
st.caption("Historical patterns (Open-Meteo backfill + Airflow hourly) and live 7-day forecasts across Germany's 10 largest cities")
st.markdown(
    "Germany sits in Central Europe with a temperate seasonal climate — "
    "warm summers, cool winters, and rain distributed fairly evenly year-round."
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

# ---------------- Sidebar: city list (single select) ----------------
city_meta = df.groupby("city_name").agg(lat=("lat", "first"), lon=("lon", "first")).reset_index()
city_meta = city_meta.sort_values("city_name")
all_cities = city_meta["city_name"].tolist()

st.sidebar.header("Cities")
selected_city = st.sidebar.radio("Select a city", all_cities, index=0, label_visibility="collapsed")

city_row = city_meta[city_meta["city_name"] == selected_city].iloc[0]
city_lat, city_lon = city_row["lat"], city_row["lon"]

tab_historical, tab_current = st.tabs(["📊 Historical Data", "🌤️ Current Weather"])

# =========================================================
# TAB 1: HISTORICAL DATA (all-city comparison + city deep dive)
# =========================================================
with tab_historical:
    min_date, max_date = df["date"].min(), df["date"].max()
    date_range = st.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
    hdf = df
    if len(date_range) == 2:
        start_d, end_d = date_range
        hdf = hdf[(hdf["date"] >= start_d) & (hdf["date"] <= end_d)]

    if hdf.empty:
        st.info("No data for this date range.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg temp (all cities)", f"{hdf['temp_c'].mean():.1f}°C")
        col2.metric("Avg humidity (all cities)", f"{hdf['humidity'].mean():.0f}%")
        col3.metric("Hottest recorded", f"{hdf['temp_c'].max():.1f}°C")
        col4.metric("Coldest recorded", f"{hdf['temp_c'].min():.1f}°C")

        st.divider()

        # ---- Map ----
        st.subheader("Cities at a glance")
        st.caption("Bubble size = population · color = average temperature (selected period)")
        map_data = hdf.groupby("city_name").agg(
            lat=("lat", "first"), lon=("lon", "first"),
            population=("population", "first"),
            avg_temp=("temp_c", "mean"), avg_humidity=("humidity", "mean"),
        ).reset_index()
        fig_map = px.scatter_mapbox(
            map_data, lat="lat", lon="lon", size="population", color="avg_temp",
            color_continuous_scale="RdYlBu_r", hover_name="city_name",
            hover_data={"population": True, "avg_temp": ":.1f", "avg_humidity": ":.0f", "lat": False, "lon": False},
            size_max=45, zoom=4.7, center={"lat": 51.1657, "lon": 10.4515},
            labels={"avg_temp": "Avg Temp (°C)", "population": "Population"},
        )
        fig_map.update_layout(mapbox_style="open-street-map", height=450, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_map, use_container_width=True)

        st.divider()

        # ---- City comparison bars ----
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Average temperature by city")
            avg_temp = hdf.groupby("city_name")["temp_c"].mean().sort_values(ascending=False).reset_index()
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
            avg_humidity = hdf.groupby("city_name")["humidity"].mean().sort_values(ascending=False).reset_index()
            fig_avg_humidity = px.bar(
                avg_humidity, x="city_name", y="humidity", color="humidity",
                color_continuous_scale="Blues", text_auto=".0f",
                labels={"humidity": "Avg Humidity (%)", "city_name": ""},
            )
            fig_avg_humidity.update_layout(showlegend=False, coloraxis_showscale=False)
            fig_avg_humidity.update_traces(textposition="outside")
            st.plotly_chart(fig_avg_humidity, use_container_width=True)

        # ---- Weather condition mix ----
        st.subheader("Weather condition mix by city")
        st.caption("Share of time spent in each condition — normalized so cities are comparable")
        condition_counts = hdf.groupby(["city_name", "weather_main"]).size().reset_index(name="count")
        condition_counts["pct"] = condition_counts.groupby("city_name")["count"].transform(lambda x: x / x.sum() * 100)
        fig_cond = px.bar(
            condition_counts, x="city_name", y="pct", color="weather_main", barmode="stack",
            labels={"city_name": "", "pct": "Share of readings (%)", "weather_main": "Condition"},
        )
        st.plotly_chart(fig_cond, use_container_width=True)

        # ---- Wind speed distribution ----
        st.subheader("Wind speed distribution")
        fig_wind = px.histogram(
            hdf, x="wind_speed", color="city_name", nbins=30, opacity=0.7,
            labels={"wind_speed": "Wind speed (m/s)", "city_name": "City"},
        )
        st.plotly_chart(fig_wind, use_container_width=True)

        # ---- Summary table ----
        st.subheader("City summary")
        summary = hdf.groupby("city_name").agg(
            population=("population", "first"), avg_temp_c=("temp_c", "mean"),
            max_temp_c=("temp_c", "max"), min_temp_c=("temp_c", "min"),
            avg_humidity=("humidity", "mean"), avg_wind_speed=("wind_speed", "mean"),
        ).round(1).reset_index()
        summary.columns = ["City", "Population", "Avg Temp (°C)", "Max Temp (°C)",
                            "Min Temp (°C)", "Avg Humidity (%)", "Avg Wind (m/s)"]
        summary = summary.sort_values("Population", ascending=False)
        st.dataframe(summary, hide_index=True, use_container_width=True)

        st.divider()

        # ---- Deep dive: selected city ----
        st.subheader(f"Deep dive: {selected_city}")
        city_df = hdf[hdf["city_name"] == selected_city]

        st.markdown("**Temperature trend**")
        daily = city_df.groupby("date")["temp_c"].mean().reset_index()
        daily["rolling_7d"] = daily["temp_c"].rolling(7, min_periods=1).mean()
        fig_trend = px.line(
            daily, x="date", y=["temp_c", "rolling_7d"],
            labels={"value": "Temp (°C)", "date": "", "variable": ""},
        )
        fig_trend.data[0].name = "Daily avg"
        fig_trend.data[1].name = "7-day rolling avg"
        fig_trend.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig_trend, use_container_width=True)

        st.markdown("**Monthly temperature distribution**")
        box_df = city_df.copy()
        box_df["month_name"] = box_df["month"].apply(lambda m: MONTH_NAMES[m - 1])
        fig_box = px.box(
            box_df, x="month_name", y="temp_c",
            category_orders={"month_name": MONTH_NAMES},
            labels={"temp_c": "Temp (°C)", "month_name": ""},
        )
        st.plotly_chart(fig_box, use_container_width=True)

        with st.expander("Raw data"):
            st.dataframe(city_df.sort_values("observed_at", ascending=False), hide_index=True, use_container_width=True)

# =========================================================
# TAB 2: CURRENT WEATHER (Apple-widget style, live + 7-day)
# =========================================================
with tab_current:
    try:
        forecast = fetch_forecast(city_lat, city_lon)
    except requests.exceptions.RequestException as e:
        st.error(f"Couldn't fetch live forecast: {e}")
        st.stop()

    current = forecast["current_weather"]
    current_temp = current["temperature"]
    current_code = current["weathercode"]
    current_time = current["time"]

    daily = forecast["daily"]
    hourly = forecast["hourly"]

    # ---- Big current-conditions card (Apple widget style) ----
    st.markdown(f"### {selected_city}")
    st.caption(f"As of {datetime.fromisoformat(current_time).strftime('%A, %H:%M')}")

    card_col1, card_col2 = st.columns([1, 2])
    with card_col1:
        st.markdown(
            f"""
            <div style="text-align:center; padding: 10px 0;">
                <div style="font-size:72px; line-height:1;">{WEATHER_EMOJI.get(current_code, "🌡️")}</div>
                <div style="font-size:56px; font-weight:600; line-height:1.1;">{current_temp:.0f}°</div>
                <div style="font-size:18px; color:gray;">{WEATHER_LABEL.get(current_code, "—")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with card_col2:
        today_hi = daily["temperature_2m_max"][0]
        today_lo = daily["temperature_2m_min"][0]
        today_precip = daily["precipitation_sum"][0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Today's high", f"{today_hi:.0f}°")
        m2.metric("Today's low", f"{today_lo:.0f}°")
        m3.metric("Precipitation", f"{today_precip:.1f} mm")

        # Next 24h hourly mini chart
        now_idx = hourly["time"].index(current_time[:13] + ":00") if current_time[:13] + ":00" in hourly["time"] else 0
        next_hours = hourly["time"][now_idx: now_idx + 24]
        next_temps = hourly["temperature_2m"][now_idx: now_idx + 24]
        hourly_df = pd.DataFrame({
            "hour": [datetime.fromisoformat(t).strftime("%H:%M") for t in next_hours],
            "temp": next_temps,
        })
        fig_hourly = px.line(hourly_df, x="hour", y="temp", markers=True, labels={"temp": "°C", "hour": ""})
        fig_hourly.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_hourly, use_container_width=True)

    st.divider()

    # ---- 7-day forecast row (Apple widget style day cards) ----
    st.markdown("**7-day forecast**")
    n_days = len(daily["time"])
    all_highs = daily["temperature_2m_max"]
    all_lows = daily["temperature_2m_min"]
    range_min, range_max = min(all_lows), max(all_highs)

    day_cols = st.columns(n_days)
    for i in range(n_days):
        d = datetime.fromisoformat(daily["time"][i])
        code = daily["weathercode"][i]
        hi = daily["temperature_2m_max"][i]
        lo = daily["temperature_2m_min"][i]
        label = "Today" if i == 0 else DAY_NAMES[d.weekday()]

        with day_cols[i]:
            st.markdown(
                f"""
                <div style="text-align:center; padding: 8px 4px; border-radius: 10px; background: rgba(128,128,128,0.08);">
                    <div style="font-weight:600;">{label}</div>
                    <div style="font-size:32px; margin: 4px 0;">{WEATHER_EMOJI.get(code, "🌡️")}</div>
                    <div style="font-size:14px;">{hi:.0f}° <span style="color:gray;">{lo:.0f}°</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---- 7-day high/low range chart ----
    st.markdown("**High / low trend**")
    range_df = pd.DataFrame({
        "day": [DAY_NAMES[datetime.fromisoformat(t).weekday()] if i > 0 else "Today"
                for i, t in enumerate(daily["time"])],
        "high": all_highs,
        "low": all_lows,
    })
    fig_range = px.line(range_df, x="day", y=["high", "low"], markers=True,
                         labels={"value": "Temp (°C)", "day": "", "variable": ""})
    fig_range.data[0].name = "High"
    fig_range.data[1].name = "Low"
    fig_range.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02), height=300)
    st.plotly_chart(fig_range, use_container_width=True)

    st.caption("Live forecast from Open-Meteo, refreshed every 15 minutes.")