from pymongo import MongoClient
from pymongo.database import Database

from app.config import settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri)
    return _client


def get_db() -> Database:
    return get_client()[settings.mongo_db]


COLLECTIONS = {
    "nasa_apod": "nasa_apod",
    "pokemon": "pokemon",
    "weather": "weather",
}


SCHEMA_SKETCH = {
    "nasa_apod": {
        "description": "NASA Astronomy Picture of the Day records",
        "fields": {
            "source": "string (always 'nasa_apod')",
            "ingested_at": "ISO datetime string",
            "date": "YYYY-MM-DD",
            "title": "string",
            "explanation": "string",
            "url": "media URL",
            "media_type": "image | video",
            "copyright": "string | null",
            "hdurl": "string | null",
        },
    },
    "pokemon": {
        "description": "Pokémon basic profiles from PokéAPI",
        "fields": {
            "source": "string (always 'pokeapi')",
            "ingested_at": "ISO datetime string",
            "poke_id": "int",
            "name": "string (lowercase)",
            "height": "int (decimetres)",
            "weight": "int (hectograms)",
            "types": "string[]",
            "abilities": "string[]",
            "base_experience": "int",
            "sprite_url": "string | null",
        },
    },
    "weather": {
        "description": "Open-Meteo current + daily forecast snapshots",
        "fields": {
            "source": "string (always 'open_meteo')",
            "ingested_at": "ISO datetime string",
            "city": "string",
            "latitude": "float",
            "longitude": "float",
            "timezone": "string",
            "temperature_c": "float (current)",
            "windspeed_kmh": "float (current)",
            "weather_code": "int",
            "daily": [
                {
                    "date": "YYYY-MM-DD",
                    "temp_max_c": "float",
                    "temp_min_c": "float",
                    "precipitation_sum_mm": "float",
                }
            ],
        },
    },
}
