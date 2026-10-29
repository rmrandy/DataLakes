import json
import re
from typing import Any

import google.generativeai as genai
from pymongo.collection import Collection

from app.config import settings
from app.db import SCHEMA_SKETCH, get_db

ALLOWED_COLLECTIONS = set(SCHEMA_SKETCH.keys())
MAX_RESULTS = 25


def _require_gemini() -> None:
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to .env to enable chat."
        )
    genai.configure(api_key=settings.gemini_api_key)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Prefer fenced JSON blocks
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError(f"Could not parse JSON from model output: {text[:300]}")


def _sanitize_query(raw: dict[str, Any]) -> dict[str, Any]:
    collection = raw.get("collection")
    if collection not in ALLOWED_COLLECTIONS:
        raise ValueError(
            f"Collection '{collection}' not allowed. Use one of: {sorted(ALLOWED_COLLECTIONS)}"
        )

    op = raw.get("operation", "find")
    if op not in ("find", "aggregate"):
        raise ValueError("operation must be 'find' or 'aggregate'")

    if op == "find":
        filt = raw.get("filter") or {}
        projection = raw.get("projection")
        sort = raw.get("sort")
        limit = int(raw.get("limit") or 10)
        limit = max(1, min(limit, MAX_RESULTS))
        if not isinstance(filt, dict):
            raise ValueError("filter must be an object")
        return {
            "collection": collection,
            "operation": "find",
            "filter": filt,
            "projection": projection if isinstance(projection, dict) else None,
            "sort": sort if isinstance(sort, list) else None,
            "limit": limit,
        }

    pipeline = raw.get("pipeline") or []
    if not isinstance(pipeline, list):
        raise ValueError("pipeline must be a list")
    # Cap result size
    has_limit = any("$limit" in stage for stage in pipeline if isinstance(stage, dict))
    if not has_limit:
        pipeline = [*pipeline, {"$limit": MAX_RESULTS}]
    return {
        "collection": collection,
        "operation": "aggregate",
        "pipeline": pipeline,
    }


def _run_mongo(query: dict[str, Any]) -> list[dict[str, Any]]:
    db = get_db()
    coll: Collection = db[query["collection"]]

    if query["operation"] == "find":
        cursor = coll.find(query["filter"], query.get("projection"))
        if query.get("sort"):
            cursor = cursor.sort(query["sort"])
        cursor = cursor.limit(query["limit"])
        docs = list(cursor)
    else:
        docs = list(coll.aggregate(query["pipeline"]))

    # Make JSON-serializable (ObjectId, etc.)
    return json.loads(json.dumps(docs, default=str))


def _plan_query(question: str) -> dict[str, Any]:
    _require_gemini()
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = f"""You are a MongoDB query planner for a small demo data lake.
Answer ONLY by producing a JSON object — no prose.

Allowed collections and schemas:
{json.dumps(SCHEMA_SKETCH, indent=2)}

Rules:
- Use ONLY the collections above.
- Prefer "find" with a filter when possible; use "aggregate" for counts/grouping.
- Never invent field names.
- limit <= 25.
- If the question cannot be answered from this data, still return a best-effort find with an empty filter and limit 5, plus "unanswerable": true.

JSON shape for find:
{{
  "collection": "nasa_apod" | "pokemon" | "weather",
  "operation": "find",
  "filter": {{}},
  "projection": {{}} | null,
  "sort": [["field", 1|-1]] | null,
  "limit": 10,
  "unanswerable": false
}}

JSON shape for aggregate:
{{
  "collection": "...",
  "operation": "aggregate",
  "pipeline": [],
  "unanswerable": false
}}

User question: {question}
"""
    result = model.generate_content(prompt)
    return _sanitize_query(_extract_json(result.text or ""))


def _answer_from_results(question: str, query: dict[str, Any], results: list[dict]) -> str:
    _require_gemini()
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = f"""You answer questions ONLY using the MongoDB query results below.
If results are empty or unrelated, say you don't have that in the ingested data.
Do not invent facts. Be concise (2-6 sentences). Mention units when relevant.

Question: {question}

Executed query:
{json.dumps(query, indent=2)}

Results ({len(results)} docs):
{json.dumps(results, indent=2, default=str)}
"""
    result = model.generate_content(prompt)
    return (result.text or "").strip() or "No answer generated."


def answer_question(question: str) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        raise ValueError("question is required")

    query = _plan_query(question)
    results = _run_mongo(query)
    answer = _answer_from_results(question, query, results)

    return {
        "question": question,
        "mongo_query": query,
        "result_count": len(results),
        "results": results,
        "answer": answer,
    }
