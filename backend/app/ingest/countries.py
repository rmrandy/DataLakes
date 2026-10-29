from datetime import datetime, timezone

import httpx

from app.db import get_db

# ISO3 codes — World Bank indicators need no API key
COUNTRY_CODES = [
    "USA",
    "CRI",
    "JPN",
    "GBR",
    "BRA",
    "IND",
    "DEU",
    "FRA",
    "CAN",
    "AUS",
    "MEX",
    "CHN",
]

POP_INDICATOR = "SP.POP.TOTL"
AREA_INDICATOR = "AG.SRF.TOTL.K2"


async def _fetch_indicator(client: httpx.AsyncClient, indicator: str) -> dict[str, dict]:
    codes = ";".join(COUNTRY_CODES)
    resp = await client.get(
        f"https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}",
        params={"format": "json", "mrv": 1, "per_page": 50},
    )
    resp.raise_for_status()
    payload = resp.json()
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    out: dict[str, dict] = {}
    for row in rows or []:
        iso3 = row.get("countryiso3code")
        if not iso3:
            continue
        out[iso3] = {
            "name": (row.get("country") or {}).get("value") or iso3,
            "value": row.get("value"),
            "year": row.get("date"),
        }
    return out


async def ingest_countries() -> dict:
    """Ingest World Bank population + surface area (no API key)."""
    db = get_db()
    collection = db["countries"]
    now = datetime.now(timezone.utc).isoformat()
    docs = []

    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        population = await _fetch_indicator(client, POP_INDICATOR)
        area = await _fetch_indicator(client, AREA_INDICATOR)

    for iso3 in COUNTRY_CODES:
        pop = population.get(iso3) or {}
        ar = area.get(iso3) or {}
        if pop.get("value") is None and ar.get("value") is None:
            continue
        docs.append(
            {
                "source": "world_bank",
                "ingested_at": now,
                "name": pop.get("name") or ar.get("name") or iso3,
                "cca3": iso3,
                "population": pop.get("value"),
                "population_year": pop.get("year"),
                "area_km2": ar.get("value"),
                "area_year": ar.get("year"),
            }
        )

    if docs:
        collection.delete_many({"source": "world_bank"})
        collection.insert_many(docs)

    return {"collection": "countries", "inserted": len(docs)}
