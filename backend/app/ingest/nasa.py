from datetime import datetime, timezone

import httpx

from app.config import settings
from app.db import get_db


async def ingest_nasa_apod(days: int = 7) -> dict:
    """Ingest recent Astronomy Pictures of the Day into nasa_apod."""
    db = get_db()
    collection = db["nasa_apod"]
    now = datetime.now(timezone.utc).isoformat()

    url = "https://api.nasa.gov/planetary/apod"
    params = {
        "api_key": settings.nasa_api_key,
        "count": days,
        "thumbs": True,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        items = resp.json()

    docs = []
    for item in items:
        docs.append(
            {
                "source": "nasa_apod",
                "ingested_at": now,
                "date": item.get("date"),
                "title": item.get("title"),
                "explanation": item.get("explanation"),
                "url": item.get("url") or item.get("thumbnail_url"),
                "media_type": item.get("media_type"),
                "copyright": item.get("copyright"),
                "hdurl": item.get("hdurl"),
            }
        )

    if docs:
        # Replace snapshot for demo simplicity
        collection.delete_many({"source": "nasa_apod"})
        collection.insert_many(docs)

    return {"collection": "nasa_apod", "inserted": len(docs)}
