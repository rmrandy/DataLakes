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
    "countries": "countries",
    "crypto": "crypto",
    "fx_rates": "fx_rates",
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
        "description": "Open-Meteo current + 7-day daily forecast snapshots",
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
    "countries": {
        "description": "World Bank demographics for comparison charts (population, area)",
        "fields": {
            "source": "string (always 'world_bank')",
            "ingested_at": "ISO datetime string",
            "name": "string",
            "cca3": "ISO alpha-3 code",
            "population": "int",
            "population_year": "string YYYY",
            "area_km2": "float",
            "area_year": "string YYYY",
        },
    },
    "crypto": {
        "description": "Binance public crypto markets + 7-day USD close history (no API key)",
        "fields": {
            "source": "string (always 'binance')",
            "ingested_at": "ISO datetime string",
            "coin_id": "string",
            "name": "string",
            "symbol": "string",
            "market_symbol": "string e.g. BTCUSDT",
            "price_usd": "float",
            "volume_24h_usd": "float",
            "change_24h_pct": "float",
            "high_24h_usd": "float",
            "low_24h_usd": "float",
            "history": [{"date": "YYYY-MM-DD", "price_usd": "float"}],
        },
    },
    "fx_rates": {
        "description": "Frankfurter FX rates vs USD + 14-day history (no API key)",
        "fields": {
            "source": "string (always 'frankfurter')",
            "ingested_at": "ISO datetime string",
            "base": "string (USD)",
            "quote": "string (EUR, GBP, ...)",
            "pair": "string like USD/EUR",
            "rate": "float (latest)",
            "as_of": "YYYY-MM-DD",
            "history": [{"date": "YYYY-MM-DD", "rate": "float"}],
        },
    },
}
