from datetime import datetime, timezone

import httpx

from app.db import get_db

# Binance public market data — no API key, good numeric/time-series charts
SYMBOLS = [
    {"symbol": "BTCUSDT", "coin_id": "bitcoin", "name": "Bitcoin", "symbol_short": "BTC"},
    {"symbol": "ETHUSDT", "coin_id": "ethereum", "name": "Ethereum", "symbol_short": "ETH"},
    {"symbol": "SOLUSDT", "coin_id": "solana", "name": "Solana", "symbol_short": "SOL"},
    {"symbol": "ADAUSDT", "coin_id": "cardano", "name": "Cardano", "symbol_short": "ADA"},
    {"symbol": "DOGEUSDT", "coin_id": "dogecoin", "name": "Dogecoin", "symbol_short": "DOGE"},
    {"symbol": "XRPUSDT", "coin_id": "ripple", "name": "XRP", "symbol_short": "XRP"},
]


async def ingest_crypto() -> dict:
    """Ingest Binance 24h tickers + 7 daily klines as USD price history."""
    db = get_db()
    collection = db["crypto"]
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    symbols_json = "[" + ",".join(f'"{s["symbol"]}"' for s in SYMBOLS) + "]"

    async with httpx.AsyncClient(
        timeout=45.0,
        follow_redirects=True,
        base_url="https://api.binance.com",
    ) as client:
        tickers = await client.get(
            "/api/v3/ticker/24hr",
            params={"symbols": symbols_json},
        )
        tickers.raise_for_status()
        by_symbol = {row["symbol"]: row for row in tickers.json()}

        for meta in SYMBOLS:
            ticker = by_symbol.get(meta["symbol"]) or {}
            klines = await client.get(
                "/api/v3/klines",
                params={"symbol": meta["symbol"], "interval": "1d", "limit": 7},
            )
            klines.raise_for_status()
            history = []
            for candle in klines.json():
                # [open_time, open, high, low, close, ...]
                open_ms = int(candle[0])
                close_price = float(candle[4])
                history.append(
                    {
                        "date": datetime.fromtimestamp(
                            open_ms / 1000, tz=timezone.utc
                        ).strftime("%Y-%m-%d"),
                        "price_usd": close_price,
                    }
                )

            last_price = float(ticker["lastPrice"]) if ticker.get("lastPrice") else None
            change_pct = (
                float(ticker["priceChangePercent"])
                if ticker.get("priceChangePercent") is not None
                else None
            )
            volume_quote = (
                float(ticker["quoteVolume"]) if ticker.get("quoteVolume") else None
            )

            docs.append(
                {
                    "source": "binance",
                    "ingested_at": now,
                    "coin_id": meta["coin_id"],
                    "name": meta["name"],
                    "symbol": meta["symbol_short"],
                    "market_symbol": meta["symbol"],
                    "price_usd": last_price,
                    "volume_24h_usd": volume_quote,
                    "change_24h_pct": change_pct,
                    "high_24h_usd": float(ticker["highPrice"]) if ticker.get("highPrice") else None,
                    "low_24h_usd": float(ticker["lowPrice"]) if ticker.get("lowPrice") else None,
                    "history": history,
                }
            )

    if docs:
        collection.delete_many({"source": "binance"})
        # Also clear prior coingecko snapshots if any
        collection.delete_many({"source": "coingecko"})
        collection.insert_many(docs)

    return {"collection": "crypto", "inserted": len(docs)}
