import asyncio

from app.ingest.countries import ingest_countries
from app.ingest.crypto_markets import ingest_crypto
from app.ingest.frankfurter import ingest_fx
from app.ingest.nasa import ingest_nasa_apod
from app.ingest.openmeteo import ingest_weather
from app.ingest.pokeapi import ingest_pokemon


async def run_all_ingest() -> dict:
    nasa, pokemon, weather, countries, crypto, fx = await asyncio.gather(
        ingest_nasa_apod(),
        ingest_pokemon(),
        ingest_weather(),
        ingest_countries(),
        ingest_crypto(),
        ingest_fx(),
        return_exceptions=True,
    )

    results = []
    total = 0
    errors = []
    for item in (nasa, pokemon, weather, countries, crypto, fx):
        if isinstance(item, Exception):
            errors.append(str(item))
            continue
        results.append(item)
        total += int(item.get("inserted") or 0)

    payload: dict = {
        "ok": len(errors) == 0,
        "results": results,
        "total_inserted": total,
    }
    if errors:
        payload["errors"] = errors
    return payload
