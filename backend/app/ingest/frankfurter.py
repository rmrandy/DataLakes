from datetime import datetime, timedelta, timezone

import httpx

from app.db import get_db

BASE = "USD"
QUOTES = ["EUR", "GBP", "JPY", "CRC", "MXN", "BRL", "CAD", "AUD"]


async def ingest_fx() -> dict:
    """Ingest Frankfurter FX latest + 14-day history (no API key)."""
    db = get_db()
    collection = db["fx_rates"]
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    start = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    docs = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        base_url="https://api.frankfurter.dev/v1",
    ) as client:
        latest = await client.get(
            "/latest", params={"from": BASE, "to": ",".join(QUOTES)}
        )
        latest.raise_for_status()
        latest_data = latest.json()
        latest_rates = latest_data.get("rates") or {}

        series = await client.get(
            f"/{start}..{end}",
            params={"from": BASE, "to": ",".join(QUOTES)},
        )
        series.raise_for_status()
        series_data = series.json()
        by_date = series_data.get("rates") or {}

        for quote in QUOTES:
            history = []
            for date in sorted(by_date.keys()):
                day_rates = by_date[date] or {}
                if quote in day_rates:
                    history.append({"date": date, "rate": float(day_rates[quote])})

            docs.append(
                {
                    "source": "frankfurter",
                    "ingested_at": now_iso,
                    "base": BASE,
                    "quote": quote,
                    "pair": f"{BASE}/{quote}",
                    "rate": float(latest_rates[quote]) if quote in latest_rates else None,
                    "as_of": latest_data.get("date"),
                    "history": history,
                }
            )

    if docs:
        collection.delete_many({"source": "frankfurter"})
        collection.insert_many(docs)

    return {"collection": "fx_rates", "inserted": len(docs)}
