# DataLakes

Demo local de data lake: ingesta de APIs públicas → **MongoDB** → chat que responde **solo** con datos ingeridos (Gemini).

## Fuentes

| Fuente | Colección | Qué se guarda |
|--------|-----------|---------------|
| NASA APOD | `nasa_apod` | título, explicación, fecha, URL, media_type |
| PokéAPI | `pokemon` | nombre, tipos, habilidades, altura, peso |
| Open-Meteo | `weather` | ciudad, temp actual, viento, forecast 3 días |

Cada documento incluye `source` e `ingested_at`.

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

## Esquema (sketch)

```text
nasa_apod  { source, ingested_at, date, title, explanation, url, media_type, copyright?, hdurl? }
pokemon    { source, ingested_at, poke_id, name, height, weight, types[], abilities[], base_experience, sprite_url? }
weather    { source, ingested_at, city, latitude, longitude, timezone, temperature_c, windspeed_kmh, weather_code, daily[{date,temp_max_c,temp_min_c,precipitation_sum_mm}] }
```

`GET /schema` devuelve el sketch y conteos actuales.

## Preguntas de ejemplo

1. What is today's NASA astronomy picture about?
2. Which Pokémon are electric type?
3. How tall and heavy is Pikachu?
4. What is the current temperature in San Jose?
5. Which city has the highest temperature right now?

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
