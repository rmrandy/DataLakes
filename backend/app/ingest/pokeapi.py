from datetime import datetime, timezone

import httpx

from app.db import get_db

# A small, interesting demo set (ids are stable in PokéAPI)
POKE_IDS = [1, 4, 7, 25, 39, 52, 94, 133, 150, 151, 6, 9, 130, 143, 249]


async def ingest_pokemon() -> dict:
    """Ingest a fixed set of Pokémon into pokemon collection."""
    db = get_db()
    collection = db["pokemon"]
    now = datetime.now(timezone.utc).isoformat()
    docs = []

    async with httpx.AsyncClient(timeout=30.0, base_url="https://pokeapi.co/api/v2") as client:
        for poke_id in POKE_IDS:
            resp = await client.get(f"/pokemon/{poke_id}")
            resp.raise_for_status()
            data = resp.json()
            docs.append(
                {
                    "source": "pokeapi",
                    "ingested_at": now,
                    "poke_id": data["id"],
                    "name": data["name"],
                    "height": data["height"],
                    "weight": data["weight"],
                    "types": [t["type"]["name"] for t in data.get("types", [])],
                    "abilities": [a["ability"]["name"] for a in data.get("abilities", [])],
                    "base_experience": data.get("base_experience"),
                    "sprite_url": (data.get("sprites") or {}).get("front_default"),
                }
            )

    if docs:
        collection.delete_many({"source": "pokeapi"})
        collection.insert_many(docs)

    return {"collection": "pokemon", "inserted": len(docs)}
