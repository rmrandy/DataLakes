import asyncio

from app.ingest.nasa import ingest_nasa_apod
from app.ingest.openmeteo import ingest_weather
from app.ingest.pokeapi import ingest_pokemon


async def run_all_ingest() -> dict:
    nasa, pokemon, weather = await asyncio.gather(
        ingest_nasa_apod(),
        ingest_pokemon(),
        ingest_weather(),
    )
    return {
        "ok": True,
        "results": [nasa, pokemon, weather],
        "total_inserted": nasa["inserted"] + pokemon["inserted"] + weather["inserted"],
    }
