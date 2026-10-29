import { FormEvent, useEffect, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
);

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const EXAMPLES = [
  "Compare population and area of the ingested countries",
  "Compare current USD prices of ingested cryptocurrencies",
  "Show Bitcoin 7-day price history",
  "What is the USD to EUR exchange rate and its recent history?",
  "Compare current temperatures across cities",
  "Compare height and weight of the ingested Pokémon",
];

type ChatResponse = {
  question: string;
  mongo_query: Record<string, unknown>;
  result_count: number;
  results: Record<string, unknown>[];
  answer: string;
};

type ComparisonSection = {
  type: "comparison";
  title: string;
  columns: string[];
  rows: string[][];
};

type ChartSection = {
  type: "chart";
  title: string;
  chart_type: "bar" | "line";
  labels: string[];
  datasets: { label: string; data: (number | null)[] }[];
  source_fields?: { label: string; values: string[] };
};

type ReportSection = ComparisonSection | ChartSection;

type ReportResponse = {
  title: string;
  question: string;
  answer: string;
  result_count: number;
  sections: ReportSection[];
  markdown: string;
  html: string;
  grounding: string;
};

type SchemaResponse = {
  counts: Record<string, number>;
};

const CHART_COLORS = ["#3dcf8e", "#5bb8e8", "#e8b84a", "#c788e0"];

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ChartBlock({ section }: { section: ChartSection }) {
  const data = {
    labels: section.labels,
    datasets: section.datasets.map((ds, i) => ({
      label: ds.label,
      data: ds.data,
      backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + "cc",
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      borderWidth: 2,
      tension: 0.25,
    })),
  };
  const options = {
    responsive: true,
    plugins: {
      legend: { position: "top" as const },
      title: { display: false, text: section.title },
    },
    scales: {
      y: {
        // Line/time series often look flat if forced to zero (e.g. BTC prices)
        beginAtZero: section.chart_type !== "line",
      },
    },
  };

  return (
    <div className="chart-wrap">
      <h3>{section.title}</h3>
      {section.chart_type === "line" ? (
        <Line data={data} options={options} />
      ) : (
        <Bar data={data} options={options} />
      )}
      {section.source_fields && (
        <p className="meta">
          Campos: {section.source_fields.label} →{" "}
          {section.source_fields.values.join(", ")}
        </p>
      )}
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [counts, setCounts] = useState<Record<string, number> | null>(null);

  async function refreshSchema() {
    try {
      const res = await fetch(`${API_URL}/schema`);
      if (!res.ok) return;
      const data = (await res.json()) as SchemaResponse;
      setCounts(data.counts);
    } catch {
      /* ignore until API is up */
    }
  }

  useEffect(() => {
    void refreshSchema();
  }, []);

  async function runIngest() {
    setIngesting(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/ingest`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Ingest failed");
      await refreshSchema();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIngesting(false);
    }
  }

  async function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    setReport(null);
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Chat failed");
      const chat = data as ChatResponse;
      setResponse(chat);

      // Chat intent: if the user asked for a report/document, generate it automatically
      if (/\b(report|reporte|documento|compar(a|e)|chart|gr[aá]fico)\b/i.test(trimmed)) {
        await generateReport(chat);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function generateReport(from?: ChatResponse) {
    const source = from ?? response;
    if (!source) return;
    setReporting(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: source.question,
          answer: source.answer,
          results: source.results,
          mongo_query: source.mongo_query,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Report failed");
      setReport(data as ReportResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReporting(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  const slug = (report?.title || "datalakes-report")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48);

  return (
    <div className="app">
      <header>
        <h1>DataLakes</h1>
        <p>
          Demo local: APIs públicas → MongoDB → chat con Gemini que responde
          solo con datos ingeridos. Tras cada respuesta puedes generar un
          documento con comparaciones y gráficos anclados a esos resultados.
        </p>
      </header>

      <div className="toolbar">
        <button type="button" onClick={() => void runIngest()} disabled={ingesting}>
          {ingesting ? "Ingestando…" : "Ingestar datos"}
        </button>
        <button type="button" className="ghost" onClick={() => void refreshSchema()}>
          Refrescar conteos
        </button>
        <span className="status">
          API {API_URL}
          {counts
            ? ` · apod=${counts.nasa_apod ?? 0} poke=${counts.pokemon ?? 0} wx=${counts.weather ?? 0} countries=${counts.countries ?? 0} crypto=${counts.crypto ?? 0} fx=${counts.fx_rates ?? 0}`
            : ""}
        </span>
      </div>

      <div className="examples">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setQuestion(ex);
              void ask(ex);
            }}
            disabled={loading}
          >
            {ex}
          </button>
        ))}
      </div>

      <form className="chat-form" onSubmit={onSubmit}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Pregunta sobre datos ingeridos (APOD, Pokémon, clima, países, crypto, FX)…"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Consultando…" : "Preguntar"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {response && (
        <>
          <section className="panel">
            <h2>Respuesta</h2>
            <p className="answer">{response.answer}</p>
            <div className="report-actions">
              <button
                type="button"
                onClick={() => void generateReport()}
                disabled={reporting || response.result_count === 0}
              >
                {reporting ? "Generando documento…" : "Generar documento / reporte"}
              </button>
              {response.result_count === 0 && (
                <span className="meta">Sin resultados Mongo para documentar.</span>
              )}
            </div>
          </section>

          <section className="panel">
            <h2>Mongo query (dev)</h2>
            <p className="meta">{response.result_count} documento(s)</p>
            <pre className="query-block">
              {JSON.stringify(response.mongo_query, null, 2)}
            </pre>
          </section>

          <section className="panel">
            <h2>Resultados crudos</h2>
            <pre className="results-block">
              {JSON.stringify(response.results, null, 2)}
            </pre>
          </section>
        </>
      )}

      {report && (
        <section className="panel report-panel" id="report">
          <h2>Documento / reporte</h2>
          <h3 className="report-title">{report.title}</h3>
          <p className="meta">{report.grounding}</p>

          <div className="report-actions">
            <button
              type="button"
              className="ghost"
              onClick={() =>
                downloadBlob(`${slug || "report"}.md`, report.markdown, "text/markdown;charset=utf-8")
              }
            >
              Descargar Markdown
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() =>
                downloadBlob(`${slug || "report"}.html`, report.html, "text/html;charset=utf-8")
              }
            >
              Descargar HTML
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => {
                const w = window.open("", "_blank");
                if (!w) return;
                w.document.write(report.html);
                w.document.close();
                // Allow Chart.js scripts to load, then print → Save as PDF
                setTimeout(() => w.print(), 600);
              }}
            >
              Imprimir / PDF
            </button>
          </div>

          {report.sections.length === 0 && (
            <p className="meta">
              No se pudo armar tabla ni gráfico con estos resultados (campos no
              numéricos o un solo valor).
            </p>
          )}

          {report.sections.map((section, idx) => {
            if (section.type === "comparison") {
              return (
                <div key={`cmp-${idx}`} className="comparison-wrap">
                  <h3>{section.title}</h3>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          {section.columns.map((col) => (
                            <th key={col}>{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {section.rows.map((row, rIdx) => (
                          <tr key={rIdx}>
                            {row.map((cell, cIdx) => (
                              <td key={cIdx}>{cell}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            }
            return <ChartBlock key={`chart-${idx}`} section={section} />;
          })}
        </section>
      )}
    </div>
  );
}
