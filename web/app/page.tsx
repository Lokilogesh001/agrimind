'use client';
import { useMemo, useState } from 'react';

type Result = any;
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const defaults = {
  crop: 'Tomato',
  growth_stage: 'vegetative',
  lat: '13.08',
  lon: '80.27',
  n: '25',
  p: '45',
  k: '70',
  current_price: '2000',
  price_history: '1950,1980,2000',
  soil_type: '',
};

export default function Home() {
  const [form, setForm] = useState(defaults);
  const [image, setImage] = useState<File | null>(null);
  const [result, setResult] = useState<Result>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'advisory' | 'audit'>('advisory');

  // Feedback form state
  const [actionTaken, setActionTaken] = useState('');
  const [outcomeReported, setOutcomeReported] = useState('');
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState('');

  const update = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  async function run() {
    setLoading(true);
    setError('');
    setResult(null);
    setFeedbackStatus('');
    try {
      let data: any;
      if (image) {
        const body = new FormData();
        Object.entries(form).forEach(([k, v]) => body.append(k, v));
        body.append('image', image);
        const r = await fetch(`${API}/api/advisory/upload`, { method: 'POST', body });
        if (!r.ok) throw new Error(await r.text());
        data = await r.json();
      } else {
        const payload = {
          ...form,
          lat: form.lat ? Number(form.lat) : null,
          lon: form.lon ? Number(form.lon) : null,
          n: Number(form.n),
          p: Number(form.p),
          k: Number(form.k),
          current_price: form.current_price ? Number(form.current_price) : 0,
          price_history: form.price_history
            ? form.price_history.split(',').filter(Boolean).map(Number)
            : [],
        };
        const r = await fetch(`${API}/api/advisory`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!r.ok) throw new Error(await r.text());
        data = await r.json();
      }
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Unable to reach AgriMind API.');
    } finally {
      setLoading(false);
    }
  }

  async function submitFeedback() {
    if (!result?.run_id || !actionTaken.trim()) return;
    setFeedbackLoading(true);
    setFeedbackStatus('');
    try {
      const res = await fetch(`${API}/api/feedback`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          run_id: result.run_id,
          farmer_action_taken: actionTaken,
          outcome_reported: outcomeReported,
          comment: feedbackComment,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setFeedbackStatus('Feedback saved successfully. Thank you for closing the advisory loop.');
      setActionTaken('');
      setOutcomeReported('');
      setFeedbackComment('');
    } catch (e: any) {
      setFeedbackStatus(`Error saving feedback: ${e.message}`);
    } finally {
      setFeedbackLoading(false);
    }
  }

  const agents = useMemo(() => {
    if (!result) return [];
    const weatherStatus = result.weather.status || (result.weather.is_available === false ? 'UNAVAILABLE' : 'AVAILABLE');
    const weatherDesc = result.weather.is_available === false
      ? `Weather service [${weatherStatus}]: ${result.weather.reason || 'offline'}`
      : (result.weather.reason || `Rain risk ${Number(result.weather.rainfall_risk).toFixed(2)}`);

    const provTag = result.soil.provenance?.crop_target_provenance
      ? ` [${result.soil.provenance.crop_target_provenance.replace('project_calibration_', '')}]`
      : '';
    const soilDesc = `Deficiency ${Number(result.soil.overall_deficiency).toFixed(2)} (${result.soil.priority_nutrient || 'balanced'})${provTag}`;

    const diseaseDesc = result.disease.predicted_class
      ? (result.disease.normalized_disease
          ? `${result.disease.predicted_class} (${result.disease.normalized_disease}) · severity: ${result.disease.severity} (heuristic)`
          : `${result.disease.predicted_class} · severity: ${result.disease.severity} (heuristic)`)
      : 'No leaf image provided (mode C safe)';

    const advisoryDesc = result.advisory.preliminary_recommendation || 'monitor';

    const marketStatus = result.market.status || (result.market.is_available === false ? 'UNAVAILABLE' : 'AVAILABLE');
    const marketDesc = result.market.is_available === false
      ? `Market signal [${marketStatus}]: hold fallback`
      : `Signal: ${result.market.signal} (score ${Number(result.market.market_score || 0).toFixed(2)}) [${marketStatus}]`;

    return [
      ['Weather', result.weather.confidence ?? 0.0, weatherDesc],
      ['Soil', result.soil.confidence ?? 0.9, soilDesc],
      ['Disease', result.disease.confidence ?? 0.0, diseaseDesc],
      ['Advisory', result.advisory.confidence ?? 0.0, advisoryDesc],
      ['Market', result.market.confidence ?? 0.0, marketDesc],
    ];
  }, [result]);

  return (
    <main>
      <header>
        <div>
          <span className="eyebrow">OBSERVABLE MULTI-AGENT AGRICULTURE</span>
          <h1>AgriMind</h1>
          <p>Five specialist agents. One deterministic decision. Every step auditable.</p>
        </div>
        <div className="status"><i /> Policy engine online</div>
      </header>

      <section className="hero">
        <div>
          <span className="eyebrow">FARM ADVISORY WORKSPACE</span>
          <h2>Turn fragmented farm signals into one explainable action.</h2>
          <p>Weather safety comes first. Disease confidence is gated. Market context can optimize, but never override agronomic safety.</p>
        </div>
        <div className="pipeline">
          {['Weather', 'Soil', 'Disease', 'Advisory', 'Market', 'Decision'].map((x, i) => (
            <span key={x}>{i ? '→ ' : ''}{x}</span>
          ))}
        </div>
      </section>

      <section className="grid">
        <div className="panel">
          <div className="panelhead">
            <div>
              <span className="eyebrow">INPUT</span>
              <h2>Farm context</h2>
            </div>
            <span className="pill">Optional leaf image</span>
          </div>
          <div className="form">
            {[
              ['crop', 'Crop'],
              ['growth_stage', 'Growth stage'],
              ['lat', 'Latitude'],
              ['lon', 'Longitude'],
              ['n', 'Nitrogen (N)'],
              ['p', 'Phosphorus (P)'],
              ['k', 'Potassium (K)'],
              ['current_price', 'Current price'],
              ['price_history', 'Price history'],
              ['soil_type', 'Soil type'],
            ].map(([k, l]) => (
              <label key={k}>
                {l}
                <input value={(form as any)[k]} onChange={e => update(k, e.target.value)} />
              </label>
            ))}
          </div>
          <label className="upload">
            Leaf photograph (optional)
            <input type="file" accept="image/*" onChange={e => setImage(e.target.files?.[0] || null)} />
            <small>{image ? image.name : 'Optional: JPG, PNG or WEBP (leave empty for data-only advisory)'}</small>
          </label>
          <button onClick={run} disabled={loading}>
            {loading ? 'Running the agent graph…' : 'Run AgriMind advisory'}
          </button>
          {error && <div className="error">{error}</div>}
        </div>

        <div className="panel resultpanel">
          <div className="tabs">
            <button className={tab === 'advisory' ? 'active' : ''} onClick={() => setTab('advisory')}>
              Advisory
            </button>
            <button className={tab === 'audit' ? 'active' : ''} onClick={() => setTab('audit')}>
              Audit trail
            </button>
          </div>

          {!result ? (
            <div className="empty">
              <div className="emptyicon">AM</div>
              <h3>Ready for a farm scenario</h3>
              <p>Enter soil, weather/location, and market context. Add a leaf image when disease detection is desired.</p>
            </div>
          ) : tab === 'advisory' ? (
            <>
              <div className="decisionlabel">FINAL DECISION</div>
              <div className="decision">{String(result.recommendation).replaceAll('_', ' ')}</div>
              <p className="explanation">{result.explanation}</p>
              <div className="metrics">
                <Metric n={result.weather.rainfall_risk} l="Rain risk" />
                <Metric n={result.soil.overall_deficiency} l="Soil deficiency" />
                <Metric n={result.disease.confidence} l="Disease confidence" />
                <Metric n={result.market.market_score} l="Market score" />
              </div>

              {result.llm && result.llm.provider && (
                <div className="llmcard">
                  <b>Explanation Layer: {result.llm.provider} ({result.llm.model})</b>
                  <span>Status: {result.llm.status} · Latency: {result.llm.latency_ms ?? 0} ms {result.llm.fallback_used ? '· (fallback used)' : ''}</span>
                </div>
              )}

              <h3>Agent findings</h3>
              <div className="agents">
                {agents.map(([name, confidence, detail]) => (
                  <div className="agent" key={name as string}>
                    <div>
                      <b>{name}</b>
                      <span>{detail}</span>
                    </div>
                    <strong>{Number(confidence || 0).toFixed(2)}</strong>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div>
              <h3>Execution trace</h3>
              <div className="trace">
                {result.execution_trace.map((x: string, i: number) => (
                  <div key={i}>
                    <span>{String(i + 1).padStart(2, '0')}</span>
                    {x}
                  </div>
                ))}
              </div>
              <h3>Conflicts & Overrides</h3>
              {result.conflicts?.length ? (
                <div className="trace">
                  {result.conflicts.map((c: any, i: number) => (
                    <div key={i}>
                      <span>{c.priority !== null && c.priority !== undefined ? `P${c.priority}` : 'Stage 2'}</span>
                      {c.agent_a} → {c.agent_b}: {c.issue} → {c.resolution}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No Stage-1 conflict was recorded for this run.</p>
              )}
            </div>
          )}
        </div>
      </section>

      {result && (
        <section className="panel">
          <div className="panelhead">
            <div>
              <span className="eyebrow">OBSERVABILITY</span>
              <h2>Evidence & persisted run</h2>
            </div>
            <span className="runid">{result.run_id}</span>
          </div>

          <div className="evidence">
            {(result.evidence || []).map((e: any) => (
              <div key={e.id}>
                <b>{e.metadata?.source_document || 'Knowledge source'}</b>
                <span>Page {e.metadata?.source_page || '—'} · chunk {e.metadata?.chunk || '—'} · score {e.score}</span>
                <p>{e.text}</p>
              </div>
            ))}
          </div>

          <h3>Report Field Outcome (Feedback)</h3>
          <div style={{ display: 'grid', gap: '10px', marginTop: '10px' }}>
            <label>
              Action taken by farmer
              <input
                placeholder="e.g. Applied recommended fertilizer; delayed spraying due to rain"
                value={actionTaken}
                onChange={e => setActionTaken(e.target.value)}
              />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <label>
                Crop outcome observed
                <input
                  placeholder="e.g. Foliage recovered; no blight spread"
                  value={outcomeReported}
                  onChange={e => setOutcomeReported(e.target.value)}
                />
              </label>
              <label>
                Comments or field notes
                <input
                  placeholder="e.g. Follow-up soil check in 14 days"
                  value={feedbackComment}
                  onChange={e => setFeedbackComment(e.target.value)}
                />
              </label>
            </div>
            <button
              onClick={submitFeedback}
              disabled={feedbackLoading || !actionTaken.trim()}
              style={{ width: 'fit-content', marginTop: '6px' }}
            >
              {feedbackLoading ? 'Saving feedback…' : 'Submit field feedback'}
            </button>
            {feedbackStatus && <div className="muted" style={{ fontWeight: 600 }}>{feedbackStatus}</div>}
          </div>

          <details style={{ marginTop: '20px' }}>
            <summary>Raw audit JSON</summary>
            <pre>{JSON.stringify(result.audit, null, 2)}</pre>
          </details>
        </section>
      )}

      <footer>AgriMind prototype · deterministic policy is authoritative · model confidence is not a substitute for field agronomy judgement.</footer>
    </main>
  );
}

function Metric({ n, l }: { n: number; l: string }) {
  return (
    <div>
      <strong>{Number(n || 0).toFixed(2)}</strong>
      <span>{l}</span>
    </div>
  );
}
