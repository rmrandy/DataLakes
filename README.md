# DataLakes

Demo local de data lake: ingesta de APIs públicas → **MongoDB** → chat que responde **solo** con datos ingeridos (Gemini) → documentos con comparaciones y gráficos.

## Fuentes

| Fuente | Colección | API key | Qué se guarda |
|--------|-----------|---------|---------------|
| NASA APOD | `nasa_apod` | opcional (`DEMO_KEY` o key gratis) | título, explicación, fecha, URL, media_type |
| PokéAPI | `pokemon` | no | nombre, tipos, habilidades, altura, peso |
| Open-Meteo | `weather` | no | ciudad, temp actual, viento, forecast **7 días** |
| World Bank | `countries` | no | población y área km² (comparaciones) |
| Binance public | `crypto` | no | precio USD, volumen 24h, historial diario 7 días |
| Frankfurter | `fx_rates` | no | FX vs USD (latest + historial 14 días) |

Cada documento incluye `source` e `ingested_at`. World Bank / Binance / Frankfurter / Open-Meteo son especialmente útiles para **tablas de comparación** y **gráficos** numéricos o de series temporales. (REST Countries v3 está deprecado y CoinGecko rate-limita demos; por eso usamos World Bank + Binance.)

## Requisitos

- Docker + Docker Compose
- Una `GEMINI_API_KEY` ([Google AI Studio](https://aistudio.google.com/apikey))

## Cómo correr

```bash
cp .env.example .env
# Edita .env y pon GEMINI_API_KEY=...

docker compose up --build
```

Servicios:

- API: http://localhost:8000  (docs en `/docs`)
- UI:  http://localhost:5173
- MongoDB: `localhost:27017`

### 1. Ingestar

En la UI pulsa **Ingestar datos**, o:

```bash
curl -X POST http://localhost:8000/ingest
```

### 2. Chatear

Pregunta en la UI, o:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Which Pokémon are electric type?"}'
```

El flujo del chat:

1. Gemini genera un `find` / `aggregate` contra el esquema conocido.
2. La API lo ejecuta en MongoDB.
3. Gemini formula la respuesta **solo** con esos resultados.
4. La UI muestra la query generada (panel “Mongo query”).

## Reportes (comparaciones y gráficos)

Tras una respuesta con resultados Mongo, en la UI pulsa **Generar documento / reporte** (o incluye en la pregunta palabras como *report*, *reporte*, *comparar*, *chart*, *gráfico* para dispararlo automáticamente).

El endpoint `POST /report` recibe la pregunta, la respuesta Gemini y los **resultados crudos** del chat. Gemini solo sugiere qué columnas/campos usar; **las filas de la tabla y los valores del gráfico se leen de esos resultados** (no se inventan números).

Artefactos:

- Tabla de **comparación** entre entidades/fuentes
- **Gráfico** bar/line (Chart.js en la UI; el HTML exportado incluye Chart.js por CDN)
  - Barras entre entidades (`population`, `price_usd`, `temperature_c`, …)
  - Líneas desde arrays anidados (`history`, `daily`) cuando el resultado es una serie temporal
- Export **Markdown** y **HTML**; en HTML usa **Imprimir / PDF** del navegador

Ejemplo API:

```bash
# 1) Consulta
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Compare population and area of the ingested countries"}' \
  > /tmp/chat.json

# 2) Reporte a partir de esa respuesta
curl -s -X POST http://localhost:8000/report \
  -H 'Content-Type: application/json' \
  -d @/tmp/chat.json | jq '{title, grounding, sections: [.sections[] | {type, title}]}'
```

### Cómo probar una comparación + un gráfico

1. `docker compose up --build` e **Ingestar datos**.
2. **Comparación (barras):** `Compare population and area of the ingested countries` → **Generar documento / reporte** → tabla + chart de `population` / `area_km2`.
3. **Serie temporal (línea):** `Show Bitcoin 7-day price history` → reporte con línea desde `history[].price_usd`.
4. Alternativas: `Compare current USD prices of ingested cryptocurrencies`, `Compare USD to EUR GBP JPY exchange rates`, `Compare current temperatures across cities`.
5. Descarga `.md` / `.html`, o **Imprimir / PDF**.

## Esquema (sketch)

```text
nasa_apod  { source, ingested_at, date, title, explanation, url, media_type, copyright?, hdurl? }
pokemon    { source, ingested_at, poke_id, name, height, weight, types[], abilities[], base_experience, sprite_url? }
weather    { source, ingested_at, city, latitude, longitude, timezone, temperature_c, windspeed_kmh, weather_code, daily[{date,temp_max_c,temp_min_c,precipitation_sum_mm}] }
countries  { source, ingested_at, name, cca3, population, population_year, area_km2, area_year }
crypto     { source, ingested_at, coin_id, name, symbol, market_symbol, price_usd, volume_24h_usd, change_24h_pct, high_24h_usd, low_24h_usd, history[{date,price_usd}] }
fx_rates   { source, ingested_at, base, quote, pair, rate, as_of, history[{date,rate}] }
```

`GET /schema` devuelve el sketch y conteos actuales.

## Preguntas de ejemplo

1. What is today's NASA astronomy picture about?
2. Which Pokémon are electric type?
3. How tall and heavy is Pikachu?
4. What is the current temperature in San Jose?
5. Which city has the highest temperature right now?
6. Compare height and weight of the ingested Pokémon
7. Compare current temperatures across cities
8. Compare population and area of the ingested countries
9. Compare current USD prices of ingested cryptocurrencies
10. Show Bitcoin 7-day price history
11. What is the USD to EUR exchange rate and its recent history?
12. Generate a report comparing country populations

## Desarrollo sin Compose (opcional)

```bash
# Terminal 1 — Mongo
docker run --rm -p 27017:27017 mongo:7

# Terminal 2 — API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# MONGO_URI=mongodb://localhost:27017 GEMINI_API_KEY=... 
uvicorn app.main:app --reload --port 8000

# Terminal 3 — UI
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

## Seguridad

- No commitees `.env`. Usa `.env.example` como plantilla.
- `NASA_API_KEY` puede quedar en `DEMO_KEY` para la demo; opcionalmente usa una key propia de https://api.nasa.gov.
- World Bank, Binance, Frankfurter y Open-Meteo **no requieren API key** para esta demo.
