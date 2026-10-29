"""Build comparison/chart documents strictly from Mongo query results."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any

NUMERIC_HINTS = (
    "height",
    "weight",
    "temperature",
    "temp_",
    "wind",
    "precipitation",
    "base_experience",
    "latitude",
    "longitude",
    "poke_id",
    "weather_code",
    "population",
    "area",
    "price",
    "market_cap",
    "volume",
    "change_",
    "rate",
    "magnitude",
)

SERIES_KEYS = ("history", "daily", "series", "prices")


def _flatten(doc: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in doc.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, path))
        elif isinstance(value, list):
            if value and all(isinstance(x, (str, int, float, bool)) or x is None for x in value):
                flat[path] = ", ".join("" if x is None else str(x) for x in value)
            elif value and all(isinstance(x, dict) for x in value):
                # Keep first numeric series from list-of-dicts for chart hints
                for i, item in enumerate(value[:5]):
                    flat.update(_flatten(item, f"{path}[{i}]"))
            else:
                flat[path] = json.dumps(value, default=str)
        else:
            flat[path] = value
    return flat


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _field_candidates(results: list[dict[str, Any]]) -> dict[str, str]:
    """Return flat field -> type hint (string|number)."""
    types: dict[str, str] = {}
    for doc in results:
        for key, value in _flatten(doc).items():
            if key.startswith("_") or key in ("source", "ingested_at", "sprite_url", "url", "hdurl"):
                continue
            if _is_number(value):
                types[key] = "number"
            elif isinstance(value, str) and key not in types:
                types[key] = "string"
    return types


def _get_path(doc: dict[str, Any], path: str) -> Any:
    # Support dotted paths and list indices like daily[0].temp_max_c
    current: Any = doc
    parts = re.split(r"\.(?![^\[]*\])", path)
    for part in parts:
        m = re.match(r"^([^\[]+)(?:\[(\d+)\])?$", part)
        if not m or not isinstance(current, dict):
            return None
        name, idx = m.group(1), m.group(2)
        current = current.get(name)
        if idx is not None:
            if not isinstance(current, list):
                return None
            i = int(idx)
            if i >= len(current):
                return None
            current = current[i]
    return current


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    return str(value)


def _auto_plan(results: list[dict[str, Any]], question: str) -> dict[str, Any]:
    fields = _field_candidates(results)
    string_fields = [k for k, t in fields.items() if t == "string"]
    number_fields = [k for k, t in fields.items() if t == "number"]

    # Prefer friendly label fields
    label_priority = (
        "name",
        "city",
        "pair",
        "symbol",
        "quote",
        "title",
        "date",
        "media_type",
    )
    label_field = next((f for f in label_priority if f in string_fields), None)
    if label_field is None and string_fields:
        label_field = string_fields[0]

    # Prefer meaningful numerics
    preferred_nums = [
        f
        for f in number_fields
        if any(h in f.lower() for h in NUMERIC_HINTS)
    ] or number_fields[:3]

    columns = []
    if label_field:
        columns.append(label_field)
    columns.extend(preferred_nums[:4])
    if not columns:
        columns = list(fields.keys())[:5]

    chart_values = preferred_nums[:2]
    plan: dict[str, Any] = {
        "title": f"Report: {question[:80]}",
        "include_comparison": bool(results),
        "comparison_columns": columns,
        "include_chart": bool(label_field and chart_values),
        "chart": {
            "chart_type": "bar",
            "label_field": label_field,
            "value_fields": chart_values,
            "title": "Numeric comparison from query results",
        }
        if label_field and chart_values
        else None,
    }
    return plan


def _build_comparison(
    results: list[dict[str, Any]], columns: list[str]
) -> dict[str, Any] | None:
    allowed = _field_candidates(results)
    cols = [c for c in columns if c in allowed]
    if not cols:
        cols = list(allowed.keys())[:5]
    if not cols or not results:
        return None
    rows = [[_cell(_get_path(doc, c)) for c in cols] for doc in results]
    return {
        "type": "comparison",
        "title": "Comparison from query results",
        "columns": cols,
        "rows": rows,
    }


def _series_from_doc(doc: dict[str, Any]) -> dict[str, Any] | None:
    """Build a line chart from nested history/daily arrays in one document."""
    for key in SERIES_KEYS:
        rows = doc.get(key)
        if not isinstance(rows, list) or not rows:
            continue
        if not all(isinstance(r, dict) for r in rows):
            continue
        label_key = next(
            (k for k in ("date", "time", "day", "timestamp") if k in rows[0]),
            None,
        )
        if not label_key:
            continue
        numeric_keys = [
            k for k, v in rows[0].items() if k != label_key and _is_number(v)
        ]
        if not numeric_keys:
            continue
        labels = [_cell(r.get(label_key)) for r in rows]
        datasets = [
            {
                "label": nk,
                "data": [
                    float(r[nk]) if _is_number(r.get(nk)) else None for r in rows
                ],
            }
            for nk in numeric_keys[:3]
        ]
        entity = (
            doc.get("name")
            or doc.get("city")
            or doc.get("pair")
            or doc.get("symbol")
            or doc.get("coin_id")
            or "series"
        )
        return {
            "type": "chart",
            "title": f"{entity} time series ({key})",
            "chart_type": "line",
            "labels": labels,
            "datasets": datasets,
            "source_fields": {"label": f"{key}.{label_key}", "values": numeric_keys},
        }
    return None


def _build_chart(
    results: list[dict[str, Any]], chart_plan: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not results:
        return None

    fields = _field_candidates(results)
    if chart_plan:
        label_field = chart_plan.get("label_field")
        value_fields = chart_plan.get("value_fields") or []
        if label_field in fields and fields.get(label_field) == "string":
            nums = [f for f in value_fields if fields.get(f) == "number"]
            if nums:
                labels: list[str] = []
                series: dict[str, list[float | None]] = {f: [] for f in nums}
                for doc in results:
                    labels.append(_cell(_get_path(doc, label_field)) or "?")
                    for f in nums:
                        raw = _get_path(doc, f)
                        series[f].append(float(raw) if _is_number(raw) else None)

                chart_type = (
                    chart_plan.get("chart_type")
                    if chart_plan.get("chart_type") in ("bar", "line")
                    else "bar"
                )
                return {
                    "type": "chart",
                    "title": chart_plan.get("title") or "Chart from query results",
                    "chart_type": chart_type,
                    "labels": labels,
                    "datasets": [{"label": f, "data": series[f]} for f in nums],
                    "source_fields": {"label": label_field, "values": nums},
                }

    if len(results) == 1:
        return _series_from_doc(results[0])
    return None


def _md_table(columns: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([header, sep, body])


def _render_markdown(
    title: str,
    question: str,
    answer: str,
    sections: list[dict[str, Any]],
    mongo_query: dict[str, Any],
    result_count: int,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        f"from {result_count} MongoDB result(s). Charts/tables use query results only._",
        "",
        "## Question",
        question,
        "",
        "## Answer",
        answer,
        "",
        "## Mongo query",
        "```json",
        json.dumps(mongo_query, indent=2),
        "```",
        "",
    ]
    for section in sections:
        if section["type"] == "comparison":
            lines += [
                f"## {section['title']}",
                "",
                _md_table(section["columns"], section["rows"]),
                "",
            ]
        elif section["type"] == "chart":
            lines += [
                f"## {section['title']} ({section['chart_type']} chart)",
                "",
                "_Interactive chart available in the UI / HTML export. Values:_",
                "",
            ]
            cols = ["label", *[ds["label"] for ds in section["datasets"]]]
            rows = []
            for i, label in enumerate(section["labels"]):
                row = [label]
                for ds in section["datasets"]:
                    val = ds["data"][i]
                    row.append("" if val is None else str(val))
                rows.append(row)
            lines += [_md_table(cols, rows), ""]
    return "\n".join(lines).strip() + "\n"


def _render_html(
    title: str,
    question: str,
    answer: str,
    sections: list[dict[str, Any]],
    mongo_query: dict[str, Any],
    result_count: int,
) -> str:
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="es"><head><meta charset="utf-8"/>',
        f"<title>{html.escape(title)}</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#14201a;background:#f4f7f5}",
        "h1,h2{letter-spacing:-.02em} table{border-collapse:collapse;width:100%;margin:1rem 0}",
        "th,td{border:1px solid #c5d2cb;padding:.5rem .65rem;text-align:left} th{background:#e3ece7}",
        "pre{background:#eef3f0;padding:1rem;overflow:auto;border-radius:8px}",
        ".chart-wrap{max-width:720px;margin:1.25rem 0;background:#fff;padding:1rem;border-radius:10px;border:1px solid #c5d2cb}",
        ".meta{color:#567064;font-size:.9rem}",
        "@media print{body{background:#fff}.no-print{display:none}}",
        "</style>",
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>',
        "</head><body>",
        f"<h1>{html.escape(title)}</h1>",
        f'<p class="meta">Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} '
        f"from {result_count} MongoDB result(s). Numbers come only from query results.</p>",
        "<h2>Question</h2>",
        f"<p>{html.escape(question)}</p>",
        "<h2>Answer</h2>",
        f"<p>{html.escape(answer)}</p>",
        "<h2>Mongo query</h2>",
        f"<pre>{html.escape(json.dumps(mongo_query, indent=2))}</pre>",
        '<p class="no-print"><button onclick="window.print()">Print / Save as PDF</button></p>',
    ]

    chart_scripts: list[str] = []
    for i, section in enumerate(sections):
        if section["type"] == "comparison":
            parts.append(f"<h2>{html.escape(section['title'])}</h2><table><thead><tr>")
            for col in section["columns"]:
                parts.append(f"<th>{html.escape(col)}</th>")
            parts.append("</tr></thead><tbody>")
            for row in section["rows"]:
                parts.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
            parts.append("</tbody></table>")
        elif section["type"] == "chart":
            cid = f"chart_{i}"
            parts.append(f"<h2>{html.escape(section['title'])}</h2>")
            parts.append(f'<div class="chart-wrap"><canvas id="{cid}"></canvas></div>')
            cfg = {
                "type": section["chart_type"],
                "data": {
                    "labels": section["labels"],
                    "datasets": [
                        {
                            "label": ds["label"],
                            "data": ds["data"],
                            "borderWidth": 2,
                        }
                        for ds in section["datasets"]
                    ],
                },
                "options": {
                    "responsive": True,
                    "plugins": {"legend": {"position": "top"}},
                    "scales": {
                        "y": {
                            "beginAtZero": section["chart_type"] != "line",
                        }
                    },
                },
            }
            chart_scripts.append(
                f"new Chart(document.getElementById('{cid}'), {json.dumps(cfg)});"
            )

    if chart_scripts:
        parts.append("<script>")
        parts.extend(chart_scripts)
        parts.append("</script>")
    parts.append("</body></html>")
    return "\n".join(parts)


def build_report(
    question: str,
    answer: str,
    results: list[dict[str, Any]],
    mongo_query: dict[str, Any],
) -> dict[str, Any]:
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not question:
        raise ValueError("question is required")
    if results is None:
        raise ValueError("results are required")
    if not isinstance(results, list):
        raise ValueError("results must be a list")

    # Field selection is deterministic from Mongo results (fast + grounded).
    # Chat answers still come from Gemini; report numbers are never invented.
    plan = _auto_plan(results, question)

    # Prefer nested time series when a single doc carries history/daily arrays
    series_first = len(results) == 1 and any(
        isinstance(results[0].get(k), list) and results[0].get(k) for k in SERIES_KEYS
    )

    # Always rebuild table/chart from results using field names only (no invented values)
    sections: list[dict[str, Any]] = []
    if plan.get("include_comparison", True) and not series_first:
        comparison = _build_comparison(results, plan.get("comparison_columns") or [])
        if comparison:
            sections.append(comparison)

    if series_first:
        series_chart = _series_from_doc(results[0])
        if series_chart:
            sections.append(series_chart)

    if plan.get("include_chart", True) and not any(s["type"] == "chart" for s in sections):
        chart = _build_chart(results, plan.get("chart"))
        if chart:
            sections.append(chart)

    # If we have entity rows but no cross-entity chart, try a nested time series
    if results and not any(s["type"] == "chart" for s in sections):
        for doc in results:
            series_chart = _series_from_doc(doc)
            if series_chart:
                sections.append(series_chart)
                break

    # If Gemini planned poorly, ensure at least one artifact when data allows
    if not sections and results:
        fallback = _auto_plan(results, question)
        comparison = _build_comparison(results, fallback.get("comparison_columns") or [])
        if comparison:
            sections.append(comparison)
        chart = _build_chart(results, fallback.get("chart"))
        if chart:
            sections.append(chart)
        elif not any(s["type"] == "chart" for s in sections):
            for doc in results:
                series_chart = _series_from_doc(doc)
                if series_chart:
                    sections.append(series_chart)
                    break

    title = str(plan.get("title") or f"Report: {question[:80]}")
    markdown = _render_markdown(
        title, question, answer, sections, mongo_query or {}, len(results)
    )
    html_doc = _render_html(
        title, question, answer, sections, mongo_query or {}, len(results)
    )

    return {
        "title": title,
        "question": question,
        "answer": answer,
        "result_count": len(results),
        "sections": sections,
        "markdown": markdown,
        "html": html_doc,
        "grounding": "All comparison rows and chart values were read from the provided MongoDB results; no numeric values were invented.",
    }
