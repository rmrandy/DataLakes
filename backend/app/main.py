from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.chat.service import answer_question
from app.db import SCHEMA_SKETCH, get_db
from app.ingest.runner import run_all_ingest
from app.reports.service import build_report

app = FastAPI(
    title="DataLakes Demo API",
    description="Ingest public APIs into MongoDB and chat over ingested data via Gemini.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ReportRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1)
    results: list[dict[str, Any]] = Field(default_factory=list)
    mongo_query: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health():
    try:
        get_db().command("ping")
        mongo = "ok"
    except Exception as exc:  # noqa: BLE001
        mongo = f"error: {exc}"
    return {"status": "ok", "mongo": mongo}


@app.get("/schema")
def schema():
    db = get_db()
    counts = {name: db[name].count_documents({}) for name in SCHEMA_SKETCH}
    return {"collections": SCHEMA_SKETCH, "counts": counts}


@app.post("/ingest")
async def ingest():
    try:
        return await run_all_ingest()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/chat")
def chat(body: ChatRequest):
    try:
        return answer_question(body.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/report")
def report(body: ReportRequest):
    """Build a Markdown/HTML report with comparisons and charts from chat results."""
    try:
        return build_report(
            question=body.question,
            answer=body.answer,
            results=body.results,
            mongo_query=body.mongo_query,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
