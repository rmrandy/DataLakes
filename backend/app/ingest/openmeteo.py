from datetime import datetime, timezone

import httpx

from app.db import get_db

CITIES = [
    {"city": "San Jose", "latitude": 9.9281, "longitude": -84.0907},
    {"city": "New York", "latitude": 40.7128, "longitude": -74.0060},
    {"city": "Tokyo", "latitude": 35.6762, "longitude": 139.6503},
    {"city": "London", "latitude": 51.5074, "longitude": -0.1278},
    {"city": "Sydney", "latitude": -33.8688, "longitude": 151.2093},
]


async def ingest_weather() -> dict:
    """Ingest current weather + 3-day forecast for demo cities."""
    db = get_db()
    collection = db["weather"]
    now = datetime.now(timezone.utc).isoformat()
    docs = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for place in CITIES:
            params = {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current_weather": True,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                # 7-day forecast gives a usable temperature time series for charts
                "forecast_days": 7,
                "timezone": "auto",
            }
            resp = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current_weather") or {}
            daily = data.get("daily") or {}
            days = []
            dates = daily.get("time") or []
            for i, date in enumerate(dates):
                days.append(
                    {
                        "date": date,
                        "temp_max_c": (daily.get("temperature_2m_max") or [None])[i],
                        "temp_min_c": (daily.get("temperature_2m_min") or [None])[i],
                        "precipitation_sum_mm": (daily.get("precipitation_sum") or [None])[i],
                    }
                )

            docs.append(
                {
                    "source": "open_meteo",
                    "ingested_at": now,
                    "city": place["city"],
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "timezone": data.get("timezone"),
                    "temperature_c": current.get("temperature"),
                    "windspeed_kmh": current.get("windspeed"),
                    "weather_code": current.get("weathercode"),
                    "daily": days,
                }
            )

    if docs:
        collection.delete_many({"source": "open_meteo"})
        collection.insert_many(docs)

    return {"collection": "weather", "inserted": len(docs)}
