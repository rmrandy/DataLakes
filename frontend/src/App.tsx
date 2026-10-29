import { FormEvent, useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const EXAMPLES = [
  "What is today's NASA astronomy picture about?",
  "Which Pokémon are electric type?",
  "How tall and heavy is Pikachu?",
  "What is the current temperature in San Jose?",
  "Which city has the highest temperature right now?",
];

type ChatResponse = {
  question: string;
  mongo_query: unknown;
  result_count: number;
  results: unknown[];
  answer: string;
};

type SchemaResponse = {
  counts: Record<string, number>;
};

export default function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<ChatResponse | null>(null);
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
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Chat failed");
      setResponse(data as ChatResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  return (
    <div className="app">
      <header>
        <h1>DataLakes</h1>
        <p>
          Demo local: APIs públicas → MongoDB → chat con Gemini que responde
          solo con datos ingeridos. La consulta Mongo generada se muestra para
          desarrollo.
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
            ? ` · nasa_apod=${counts.nasa_apod ?? 0} pokemon=${counts.pokemon ?? 0} weather=${counts.weather ?? 0}`
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
          placeholder="Pregunta solo sobre NASA APOD, Pokémon o clima ingerido…"
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
    </div>
  );
}
