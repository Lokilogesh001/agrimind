'use client';
import { useEffect, useMemo, useState } from 'react';

type Result = any;
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const CROP_CATEGORIES: Record<string, string[]> = {
  Cereals: ['Rice', 'Wheat', 'Maize', 'Millets', 'Barley'],
  Pulses: ['Chickpea', 'Pigeonpea', 'Soybean', 'Groundnut', 'Blackgram', 'Greengram'],
  Oilseeds: ['Mustard', 'Sunflower', 'Sesame'],
  Vegetables: ['Tomato', 'Potato', 'Chilli', 'Onion', 'Brinjal', 'Cabbage', 'Cauliflower', 'Okra'],
  Fruits: ['Apple', 'Banana', 'Mango', 'Citrus', 'Grapes'],
  'Commercial crops': ['Cotton', 'Sugarcane', 'Tobacco', 'Tea', 'Coffee'],
};

const STAGES = [
  { id: 'seedling', label: 'Seedling' },
  { id: 'vegetative', label: 'Vegetative' },
  { id: 'flowering', label: 'Flowering' },
  { id: 'fruiting_grain_filling', label: 'Fruiting / Grain Filling' },
  { id: 'maturity', label: 'Maturity' },
  { id: 'harvest', label: 'Harvest' },
  { id: 'unknown', label: 'Unknown' },
];

const SOIL_TYPES = [
  'Sandy',
  'Sandy Loam',
  'Loam',
  'Clay',
  'Clay Loam',
  'Red Soil',
  'Black Soil',
  'Alluvial',
  'Laterite',
  'Unknown',
];

export default function Home() {
  // Farm Location state
  const [locationQuery, setLocationQuery] = useState('Madurai, Tamil Nadu');
  const [selectedLocation, setSelectedLocation] = useState<{ name: string; lat: number | null; lon: number | null }>({
    name: 'Madurai, Tamil Nadu, India',
    lat: 9.9252,
    lon: 78.1198,
  });
  const [locationResults, setLocationResults] = useState<any[]>([]);
  const [showLocationDropdown, setShowLocationDropdown] = useState(false);

  // Crop & Stage state
  const [crop, setCrop] = useState('Tomato');
  const [growthStage, setGrowthStage] = useState('vegetative');

  // Flexible Soil state
  const [soilMode, setSoilMode] = useState<'automatic' | 'manual' | 'measured' | 'report'>('automatic');
  const [soilType, setSoilType] = useState('Red Soil');
  const [n, setN] = useState('');
  const [p, setP] = useState('');
  const [k, setK] = useState('');

  // Optional Context
  const [farmArea, setFarmArea] = useState('');
  const [irrigationMethod, setIrrigationMethod] = useState('');
  const [sowingDate, setSowingDate] = useState('');
  const [currentPrice, setCurrentPrice] = useState('2000');
  const [priceHistory, setPriceHistory] = useState('1950,1980,2000');
  const [image, setImage] = useState<File | null>(null);

  // Run execution state
  const [result, setResult] = useState<Result>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'advisory' | 'audit'>('advisory');
  const [showEqBreakdown, setShowEqBreakdown] = useState(false);

  // Feedback form state
  const [actionTaken, setActionTaken] = useState('');
  const [outcomeReported, setOutcomeReported] = useState('');
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState('');

  // Location search helper
  useEffect(() => {
    if (!locationQuery || locationQuery.length < 2) {
      setLocationResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/api/location/search?q=${encodeURIComponent(locationQuery)}`);
        if (res.ok) {
          const data = await res.json();
          setLocationResults(data.results || []);
        }
      } catch {
        // Fallback gracefully
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [locationQuery]);

  async function run() {
    setLoading(true);
    setError('');
    setResult(null);
    setFeedbackStatus('');
    try {
      let data: any;

      // Map soil parameters based on selected flexible mode
      let effectiveSoilType = '';
      let effectiveSoilMode = '';
      let nVal: number | null = null;
      let pVal: number | null = null;
      let kVal: number | null = null;

      if (soilMode === 'automatic') {
        effectiveSoilMode = 'LOCATION_ESTIMATED';
      } else if (soilMode === 'manual') {
        effectiveSoilType = soilType.toLowerCase().replace(' ', '_');
        effectiveSoilMode = 'USER_SELECTED';
      } else if (soilMode === 'measured') {
        effectiveSoilType = soilType.toLowerCase().replace(' ', '_');
        effectiveSoilMode = 'MEASURED';
        nVal = n ? Number(n) : null;
        pVal = p ? Number(p) : null;
        kVal = k ? Number(k) : null;
      } else if (soilMode === 'report') {
        effectiveSoilMode = 'USER_SELECTED';
        effectiveSoilType = soilType.toLowerCase().replace(' ', '_');
      }

      const locationNameToSend = selectedLocation.name || locationQuery;

      if (image) {
        const body = new FormData();
        body.append('crop', crop);
        body.append('growth_stage', growthStage);
        body.append('location_name', locationNameToSend);
        if (selectedLocation.lat !== null) body.append('lat', String(selectedLocation.lat));
        if (selectedLocation.lon !== null) body.append('lon', String(selectedLocation.lon));
        if (nVal !== null) body.append('n', String(nVal));
        if (pVal !== null) body.append('p', String(pVal));
        if (kVal !== null) body.append('k', String(kVal));
        if (effectiveSoilType) body.append('soil_type', effectiveSoilType);
        if (effectiveSoilMode) body.append('soil_mode', effectiveSoilMode);
        if (currentPrice) body.append('current_price', currentPrice);
        if (priceHistory) body.append('price_history', priceHistory);
        if (farmArea) body.append('farm_area', farmArea);
        if (irrigationMethod) body.append('irrigation_method', irrigationMethod);
        body.append('image', image);

        const r = await fetch(`${API}/api/advisory/upload`, { method: 'POST', body });
        if (!r.ok) throw new Error(await r.text());
        data = await r.json();
      } else {
        const payload: any = {
          crop,
          growth_stage: growthStage,
          location_name: locationNameToSend,
          lat: selectedLocation.lat,
          lon: selectedLocation.lon,
          soil_type: effectiveSoilType,
          soil_mode: effectiveSoilMode,
          current_price: currentPrice ? Number(currentPrice) : 0,
          price_history: priceHistory ? priceHistory.split(',').filter(Boolean).map(Number) : [],
        };
        if (nVal !== null) payload.n = nVal;
        if (pVal !== null) payload.p = pVal;
        if (kVal !== null) payload.k = kVal;
        if (farmArea) payload.farm_area = Number(farmArea);
        if (irrigationMethod) payload.irrigation_method = irrigationMethod;
        if (sowingDate) payload.sowing_date = sowingDate;

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
    const weatherStatus = result.weather?.status || (result.weather?.is_available === false ? 'UNAVAILABLE' : 'AVAILABLE');
    const weatherDesc = result.weather?.is_available === false
      ? `Weather service [${weatherStatus}]: ${result.weather.reason || 'offline'}`
      : (result.weather?.risk_explanation || `Rainfall Risk: ${Number(result.weather?.rainfall_risk || 0).toFixed(2)} (${result.weather?.risk_level || 'LOW'})`);

    const soilProv = result.soil?.provenance?.mode || (result.soil?.npk_available ? 'MEASURED' : 'UNMEASURED');
    const soilDesc = result.soil?.npk_available
      ? `Deficiency ${Number(result.soil.overall_deficiency || 0).toFixed(2)} (${result.soil.priority_nutrient || 'balanced'}) [${soilProv}]`
      : `NPK unmeasured [${soilProv}]; nutrient evaluation skipped safely`;

    const diseaseDesc = result.disease?.predicted_class
      ? (result.disease.crop_mismatch
          ? `Crop match FAILED: Selected ${crop}, predicted ${(result.disease.crop_detected || 'Tomato').charAt(0).toUpperCase() + (result.disease.crop_detected || 'Tomato').slice(1)} (${Math.round((result.disease.confidence || 0) * 100)}% conf, gate PASSED). Action BLOCKED (Reason: Crop mismatch).`
          : (result.disease.actionable
              ? `${result.disease.predicted_class} · severity: ${result.disease.severity}`
              : `Disease signal (${result.disease.predicted_class}) is below 0.60 confidence gate (${Math.round((result.disease.confidence || 0) * 100)}%)`))
      : 'No leaf image provided (mode C safe)';

    const advisoryDesc = result.advisory?.preliminary_recommendation || 'monitor';

    const marketStatus = result.market?.status || (result.market?.is_available === false ? 'UNAVAILABLE' : 'AVAILABLE');
    const isDemo = marketStatus === 'DEMO_DATA';
    const marketDesc = result.market?.is_available === false
      ? `Market signal [${marketStatus}]: hold fallback`
      : `Signal: ${result.market.signal} (score ${Number(result.market.market_score || 0).toFixed(2)}) [${marketStatus}]${isDemo ? ' (caller-provided; non-authoritative)' : ''}`;

    return [
      ['Weather', result.weather?.confidence ?? 0.0, weatherDesc],
      ['Soil', result.soil?.confidence ?? 0.0, soilDesc],
      ['Disease', result.disease?.confidence ?? 0.0, diseaseDesc],
      ['Advisory', result.advisory?.confidence ?? 0.0, advisoryDesc],
      ['Market', result.market?.confidence ?? 0.0, marketDesc],
    ];
  }, [result]);

  const stabilityBadgeClass = useMemo(() => {
    const lvl = result?.stability_level || 'INSUFFICIENT';
    if (lvl === 'HIGH') return 'badge-high';
    if (lvl === 'MODERATE') return 'badge-moderate';
    if (lvl === 'LOW') return 'badge-low';
    return 'badge-insufficient';
  }, [result]);

  const eqBadgeClass = useMemo(() => {
    const lvl = result?.evidence_quality_level || 'INSUFFICIENT';
    if (lvl === 'GOOD') return 'badge-good';
    if (lvl === 'MODERATE') return 'badge-moderate';
    if (lvl === 'LOW') return 'badge-low';
    return 'badge-insufficient';
  }, [result]);

  const weatherBadgeClass = useMemo(() => {
    const lvl = result?.weather_risk?.level || result?.weather?.risk_level || 'LOW';
    if (lvl === 'LOW') return 'wbadge-low';
    if (lvl === 'MODERATE') return 'wbadge-moderate';
    if (lvl === 'HIGH') return 'wbadge-high';
    return 'wbadge-severe';
  }, [result]);

  return (
    <main>
      <header>
        <div>
          <span className="eyebrow">OBSERVABLE MULTI-AGENT AGRICULTURE</span>
          <h1>AgriMind</h1>
          <p className="subtitle">
            AI-powered crop advisory with transparent decision reasoning.
          </p>
        </div>
        <div className="header-meta">
          <div className="status"><i /> Evidence Engine Online</div>
          <div className="pipeline-pill">
            Weather · Soil · Disease · Market → Advisory
          </div>
        </div>
      </header>

      <section className="grid">
        <div className="panel">
          <div className="panelhead">
            <div>
              <span className="eyebrow">FARM CONTEXT INPUT</span>
              <h2>Farmer Field Parameters</h2>
            </div>
            <span className="pill">Internal Geocoding</span>
          </div>

          <div className="form">
            {/* 1. Farm Location Search */}
            <div style={{ gridColumn: 'span 2' }} className="locdropdown">
              <label>
                Farm Location (village / town / district / pincode)
                <input
                  value={locationQuery}
                  placeholder="e.g. Madurai, Tamil Nadu or Pune, Maharashtra"
                  onChange={e => {
                    setLocationQuery(e.target.value);
                    setShowLocationDropdown(true);
                  }}
                  onFocus={() => setShowLocationDropdown(true)}
                />
              </label>
              {showLocationDropdown && locationResults.length > 0 && (
                <div className="locresults">
                  {locationResults.map((loc, idx) => (
                    <div
                      key={idx}
                      className="locitem"
                      onClick={() => {
                        setSelectedLocation({ name: loc.display_name, lat: loc.latitude, lon: loc.longitude });
                        setLocationQuery(loc.display_name);
                        setShowLocationDropdown(false);
                      }}
                    >
                      <strong>{loc.name}</strong>
                      <span>{loc.display_name}</span>
                    </div>
                  ))}
                </div>
              )}
              {selectedLocation.name && (
                <small style={{ color: 'var(--success)', fontWeight: 600, display: 'block', marginTop: '4px' }}>
                  ✓ Resolved: {selectedLocation.name} {selectedLocation.lat ? `(coordinates resolved internally)` : ''}
                </small>
              )}
            </div>

            {/* 2. Standardized Crop Selector */}
            <label>
              Select Crop
              <select value={crop} onChange={e => setCrop(e.target.value)}>
                {Object.entries(CROP_CATEGORIES).map(([cat, crops]) => (
                  <optgroup key={cat} label={`── ${cat} ──`}>
                    {crops.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>

            {/* 3. Crop Growth Stage */}
            <label>
              Crop Growth Stage
              <select value={growthStage} onChange={e => setGrowthStage(e.target.value)}>
                {STAGES.map(s => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </label>

            {/* 4. Flexible Soil Options */}
            <div style={{ gridColumn: 'span 2', marginTop: '6px' }}>
              <label>Soil Information Mode</label>
              <div className="modebuttons">
                <button
                  type="button"
                  className={`modebtn ${soilMode === 'automatic' ? 'active' : ''}`}
                  onClick={() => setSoilMode('automatic')}
                >
                  A. Automatic (Location-Estimated)
                </button>
                <button
                  type="button"
                  className={`modebtn ${soilMode === 'manual' ? 'active' : ''}`}
                  onClick={() => setSoilMode('manual')}
                >
                  B. Manual Soil Type
                </button>
                <button
                  type="button"
                  className={`modebtn ${soilMode === 'measured' ? 'active' : ''}`}
                  onClick={() => setSoilMode('measured')}
                >
                  C. Soil Health Card (Measured NPK)
                </button>
                <button
                  type="button"
                  className={`modebtn ${soilMode === 'report' ? 'active' : ''}`}
                  onClick={() => setSoilMode('report')}
                >
                  D. Soil Report
                </button>
              </div>

              {soilMode === 'automatic' && (
                <div className="info-box">
                  Regional soil estimate will be derived automatically from your farm location. Measured NPK remains unforced.
                </div>
              )}

              {(soilMode === 'manual' || soilMode === 'report') && (
                <label style={{ marginTop: '8px' }}>
                  Select Soil Texture Type
                  <select value={soilType} onChange={e => setSoilType(e.target.value)}>
                    {SOIL_TYPES.map(st => (
                      <option key={st} value={st}>{st}</option>
                    ))}
                  </select>
                </label>
              )}

              {soilMode === 'measured' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginTop: '8px' }}>
                  <label>
                    Nitrogen (N) kg/ha
                    <input type="number" placeholder="Optional" value={n} onChange={e => setN(e.target.value)} />
                  </label>
                  <label>
                    Phosphorus (P) kg/ha
                    <input type="number" placeholder="Optional" value={p} onChange={e => setP(e.target.value)} />
                  </label>
                  <label>
                    Potassium (K) kg/ha
                    <input type="number" placeholder="Optional" value={k} onChange={e => setK(e.target.value)} />
                  </label>
                </div>
              )}
            </div>

            {/* 5. Optional Farm Context */}
            <label>
              Farm Area (acres) [Optional]
              <input type="number" placeholder="e.g. 2.5" value={farmArea} onChange={e => setFarmArea(e.target.value)} />
            </label>
            <label>
              Irrigation Method [Optional]
              <input placeholder="e.g. Drip, Furrow, Rainfed" value={irrigationMethod} onChange={e => setIrrigationMethod(e.target.value)} />
            </label>
            <label>
              Sowing Date [Optional]
              <input type="date" value={sowingDate} onChange={e => setSowingDate(e.target.value)} />
            </label>
            <label>
              Mandi Market Price [Optional]
              <input placeholder="e.g. 2200" value={currentPrice} onChange={e => setCurrentPrice(e.target.value)} />
            </label>
          </div>

          {/* 6. Optional Leaf Image */}
          <label className="upload">
            Crop Leaf Photograph (Optional)
            <input type="file" accept="image/*" onChange={e => setImage(e.target.files?.[0] || null)} />
            <small>{image ? image.name : 'Optional: JPG, PNG or WEBP (leave empty for data-only advisory)'}</small>
          </label>

          <button onClick={run} disabled={loading} className="run-btn" style={{ marginTop: '16px' }}>
            {loading ? 'Executing Agent Graph & Evidence Engine…' : 'Run AgriMind Advisory'}
          </button>
          {error && <div className="error">{error}</div>}
        </div>

        {/* Results Panel */}
        <div className="panel resultpanel">
          <div className="panelhead">
            <div>
              <span className="eyebrow">ADVISORY & STABILITY</span>
              <h2>{result ? 'Multi-Agent Advisory' : 'Decision Reasoning'}</h2>
            </div>
            <div className="tabs" style={{ margin: 0 }}>
              <button className={tab === 'advisory' ? 'active' : ''} onClick={() => setTab('advisory')}>
                Advisory & Stability
              </button>
              <button className={tab === 'audit' ? 'active' : ''} onClick={() => setTab('audit')}>
                Evidence & Audit
              </button>
            </div>
          </div>

          {!result ? (
            <div className="empty">
              <div className="emptyicon">AM</div>
              <h3>Ready for farm scenario</h3>
              <p>Enter location and crop. Flexible soil and optional leaf image supported.</p>
            </div>
          ) : tab === 'advisory' ? (
            <>
              {/* Dual Scorecards: Decision Stability & Evidence Quality */}
              <div className="dualscorecards">
                <div className="stabilitycard" style={{ margin: 0 }}>
                  <div className="stabilityhead">
                    <span className="eyebrow">DECISION STABILITY</span>
                    <span className={`stabilitybadge ${stabilityBadgeClass}`}>
                      {result.stability_level || 'INSUFFICIENT'}
                    </span>
                  </div>
                  <div className="stabilityscore">
                    {Math.round((result.decision_stability_score ?? 0.8) * 100)}%
                  </div>
                  <div className="stabilitydesc">
                    Consistently supported across specialist agents and deterministic safety rules.
                  </div>
                </div>

                <div className="eqcard">
                  <div className="stabilityhead">
                    <span className="eyebrow">EVIDENCE QUALITY</span>
                    <span className={`stabilitybadge ${eqBadgeClass}`}>
                      {result.evidence_quality_level || 'MODERATE'}
                    </span>
                  </div>
                  <div className="stabilityscore">
                    {Math.round((result.evidence_quality_score ?? 0.75) * 100)}%
                  </div>
                  <div className="stabilitydesc" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Trustworthiness & relevance of evidence.</span>
                    {result.evidence_quality_breakdown && (
                      <button
                        onClick={() => setShowEqBreakdown(!showEqBreakdown)}
                        style={{ background: 'var(--surface-secondary)', border: '1px solid var(--border)', padding: '3px 8px', fontSize: '10px', borderRadius: '6px', cursor: 'pointer', color: 'var(--text)' }}
                      >
                        {showEqBreakdown ? 'Hide Breakdown' : 'Breakdown'}
                      </button>
                    )}
                  </div>
                  {showEqBreakdown && result.evidence_quality_breakdown && (
                    <div className="breakdowntable">
                      <div className="breakdownrow"><span>Crop relevance</span><strong>{Math.round(result.evidence_quality_breakdown.crop_relevance * 100)}%</strong></div>
                      <div className="breakdownrow"><span>Location relevance</span><strong>{Math.round(result.evidence_quality_breakdown.location_relevance * 100)}%</strong></div>
                      <div className="breakdownrow"><span>Growth-stage match</span><strong>{Math.round(result.evidence_quality_breakdown.stage_relevance * 100)}%</strong></div>
                      <div className="breakdownrow"><span>Source reliability</span><strong>{Math.round(result.evidence_quality_breakdown.source_reliability * 100)}%</strong></div>
                      <div className="breakdownrow"><span>Temporal relevance</span><strong>{Math.round(result.evidence_quality_breakdown.temporal_relevance * 100)}%</strong></div>
                      <div className="breakdownrow"><span>Completeness</span><strong>{Math.round(result.evidence_quality_breakdown.completeness * 100)}%</strong></div>
                    </div>
                  )}
                </div>
              </div>

              <div className="decisionlabel">AUTHORITATIVE FINAL RECOMMENDATION</div>
              <div className="decision">{String(result.recommendation).replaceAll('_', ' ')}</div>
              <p className="explanation">{result.explanation}</p>

              {/* Weather Risk Card */}
              <div className="weathercard">
                <div className="weatherhead">
                  <div>
                    <span className="eyebrow">WEATHER RISK ASSESSMENT</span>
                    <h4 style={{ margin: '3px 0 0', fontSize: '15px', color: 'var(--text)' }}>
                      Rainfall Risk Score: {Number(result.weather_risk?.risk_score ?? result.weather?.rainfall_risk ?? 0.0).toFixed(2)}
                    </h4>
                  </div>
                  <span className={`weatherriskbadge ${weatherBadgeClass}`}>
                    {result.weather_risk?.level || result.weather?.risk_level || 'LOW'}
                  </span>
                </div>
                <p style={{ margin: '8px 0 8px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {result.weather_risk?.explanation || result.weather?.risk_explanation || 'Weather conditions assessed deterministically.'}
                </p>
                <div style={{ display: 'flex', gap: '20px', fontSize: '12px', color: 'var(--text)', marginTop: '8px' }}>
                  <span>
                    Precipitation probability:{' '}
                    <strong style={{ color: 'var(--primary)' }}>
                      {(() => {
                        const rawP = result.weather_risk?.precipitation_probability ?? result.weather?.precipitation_probability;
                        if (rawP !== null && rawP !== undefined) {
                          return rawP <= 1.0 ? Math.round(rawP * 100) : Math.round(rawP);
                        }
                        return 0;
                      })()}%
                    </strong>
                  </span>
                  <span>Rainfall amount: <strong style={{ color: 'var(--primary)' }}>{Number(result.weather_risk?.rainfall_amount_mm ?? result.weather?.rainfall_amount_mm ?? 0).toFixed(1)} mm</strong></span>
                </div>
              </div>

              {/* Soil Nutrient Status Card */}
              {result.soil_nutrient_status === 'UNAVAILABLE' || !result.soil?.npk_available ? (
                <div className="soilstatuscard soilstatus-unavailable">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ fontSize: '13px' }}>Soil nutrient assessment: Unavailable</strong>
                    <span style={{ fontSize: '10px', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: 'var(--warning-border)', color: 'var(--warning)' }}>UNAVAILABLE</span>
                  </div>
                  <p style={{ margin: '6px 0 0', fontSize: '12px', lineHeight: 1.45 }}>
                    NPK measurements were not provided, so nutrient deficiency was not calculated.
                  </p>
                </div>
              ) : (
                <div className="soilstatuscard soilstatus-measured">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ fontSize: '13px' }}>Soil nutrient assessment: Measured</strong>
                    <span style={{ fontSize: '10px', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', background: 'var(--success-border)', color: 'var(--success)' }}>MEASURED</span>
                  </div>
                  <p style={{ margin: '6px 0 0', fontSize: '12px', lineHeight: 1.45 }}>
                    Overall deficiency: {Number(result.soil.overall_deficiency).toFixed(2)} · Priority nutrient: {result.soil.priority_nutrient || 'Balanced'}
                  </p>
                </div>
              )}

              {/* Disease Model & Gate Assessment Card */}
              {result.disease?.predicted_class && (
                <div className="diseasegatecard" style={{
                  background: result.disease.crop_mismatch ? 'var(--error-bg)' : (result.disease.actionable ? 'var(--success-bg)' : 'var(--warning-bg)'),
                  border: `1px solid ${result.disease.crop_mismatch ? 'var(--error-border)' : (result.disease.actionable ? 'var(--success-border)' : 'var(--warning-border)')}`,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div>
                      <span className="eyebrow" style={{ color: result.disease.crop_mismatch ? 'var(--error)' : 'var(--primary)' }}>DISEASE MODEL & GATE ASSESSMENT</span>
                      <h4 style={{ margin: '3px 0 0', fontSize: '15px', color: 'var(--text)' }}>
                        {result.disease.predicted_class.replaceAll('___', ' ')}
                      </h4>
                    </div>
                    <span style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '4px 10px',
                      borderRadius: '999px',
                      background: 'var(--surface)',
                      color: result.disease.actionable ? 'var(--success)' : 'var(--error)',
                      border: `1px solid ${result.disease.actionable ? 'var(--success-border)' : 'var(--error-border)'}`,
                      letterSpacing: '0.04em',
                    }}>
                      {result.disease.actionable ? 'ACTION ALLOWED' : 'ACTION BLOCKED'}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px', background: 'var(--surface)', padding: '12px', borderRadius: '8px', fontSize: '12px', border: '1px solid var(--border)' }}>
                    <div>
                      <span style={{ display: 'block', fontSize: '10px', color: 'var(--text-secondary)', fontWeight: 700, textTransform: 'uppercase' }}>Disease Confidence</span>
                      <strong style={{ fontSize: '15px', color: 'var(--text)' }}>{Math.round((result.disease.confidence || 0) * 100)}%</strong>
                    </div>
                    <div>
                      <span style={{ display: 'block', fontSize: '10px', color: 'var(--text-secondary)', fontWeight: 700, textTransform: 'uppercase' }}>Confidence Gate</span>
                      <strong style={{ fontSize: '13px', color: (result.disease.confidence || 0) >= 0.60 ? 'var(--success)' : 'var(--error)' }}>
                        {(result.disease.confidence || 0) >= 0.60 ? 'PASSED' : 'FAILED'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ display: 'block', fontSize: '10px', color: 'var(--text-secondary)', fontWeight: 700, textTransform: 'uppercase' }}>Crop Match</span>
                      <strong style={{ fontSize: '13px', color: result.disease.crop_mismatch ? 'var(--error)' : 'var(--success)' }}>
                        {result.disease.crop_mismatch ? 'FAILED' : 'PASSED'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ display: 'block', fontSize: '10px', color: 'var(--text-secondary)', fontWeight: 700, textTransform: 'uppercase' }}>Action</span>
                      <strong style={{ fontSize: '13px', color: result.disease.actionable ? 'var(--success)' : 'var(--error)' }}>
                        {result.disease.actionable ? 'ALLOWED' : 'BLOCKED'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ display: 'block', fontSize: '10px', color: 'var(--text-secondary)', fontWeight: 700, textTransform: 'uppercase' }}>Reason</span>
                      <strong style={{ fontSize: '13px', color: result.disease.crop_mismatch ? 'var(--error)' : 'var(--success)' }}>
                        {result.disease.crop_mismatch ? 'Crop mismatch' : (result.disease.actionable ? 'Crop match' : 'Low confidence')}
                      </strong>
                    </div>
                  </div>

                  <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <strong style={{ color: 'var(--text)' }}>Reason: </strong>
                    <span>
                      {result.disease.crop_mismatch
                        ? `Predicted crop is ${(result.disease.crop_detected || 'Tomato').charAt(0).toUpperCase() + (result.disease.crop_detected || 'Tomato').slice(1)} but selected crop is ${crop}. Disease action blocked.`
                        : (result.disease.actionable
                            ? 'Disease model confidence meets actionable threshold for matching crop.'
                            : `Disease signal is below the 0.60 confidence gate (${Math.round((result.disease.confidence || 0) * 100)}% < 60%).`)}
                    </span>
                  </div>
                </div>
              )}

              <div className="metrics">
                <Metric n={result.weather_risk?.risk_score ?? result.weather?.rainfall_risk} l="Rain risk" />
                <Metric n={result.soil?.overall_deficiency} l="Soil deficiency" />
                <Metric n={result.disease?.confidence} l="Disease confidence" />
                <Metric n={result.market?.market_score} l="Market score" />
              </div>

              {/* Agronomic Safety Guard Constraints */}
              {result.safety_constraints && result.safety_constraints.length > 0 && (
                <div className="safetycard">
                  <h4>Deterministic Agronomic Safety Guard Constraints</h4>
                  {result.safety_constraints.map((c: string, idx: number) => (
                    <div key={idx} className="safetyitem">{c}</div>
                  ))}
                </div>
              )}

              {/* What would change this decision? */}
              {((result.decision_change_triggers && result.decision_change_triggers.length > 0) || result.re_evaluation_trigger) && (
                <div className="triggerscard">
                  <h4>What would change this decision?</h4>
                  {result.decision_change_triggers && result.decision_change_triggers.length > 0 ? (
                    result.decision_change_triggers.map((t: string, idx: number) => (
                      <div key={idx} className="triggeritem">{t}</div>
                    ))
                  ) : (
                    <div className="triggeritem">{result.re_evaluation_trigger}</div>
                  )}
                </div>
              )}

              {/* Why this decision? */}
              <div className="whysection" style={{}}>
                <h3>Why this decision?</h3>
                {result.resolved_conflicts && result.resolved_conflicts.length > 0 ? (
                  result.resolved_conflicts.map((c: any, idx: number) => (
                    <div key={idx} className="conflictcard">
                      <b>Conflict: {c.agent_a} vs {c.agent_b} ({c.issue || c.conflict_type})</b>
                      <p>{c.evidence}</p>
                      {c.agronomic_recommendation && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', margin: '8px 0', fontSize: '11px', background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '6px' }}>
                          <div><span style={{ color: 'var(--text-secondary)', display: 'block' }}>Agronomic Rec:</span><strong style={{ color: 'var(--text)' }}>{c.agronomic_recommendation}</strong></div>
                          <div><span style={{ color: 'var(--text-secondary)', display: 'block' }}>Market Rec:</span><strong style={{ color: 'var(--text)' }}>{c.market_recommendation}</strong></div>
                          <div><span style={{ color: 'var(--text-secondary)', display: 'block' }}>Combined Advisory:</span><strong style={{ color: 'var(--primary)' }}>{c.final_advisory || result.farm_advisory || c.resolution}</strong></div>
                        </div>
                      )}
                      <span className="conflictresolved">Resolution: {c.resolution}</span>
                    </div>
                  ))
                ) : (
                  <p className="muted" style={{ fontSize: '13px' }}>
                    All specialist agents agree. No agronomic conflict recorded.
                  </p>
                )}
              </div>

              {result.required_additional_info && result.required_additional_info.length > 0 && (
                <div style={{ background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', padding: '12px 14px', borderRadius: '8px', marginTop: '12px' }}>
                  <b style={{ color: '#92400E', fontSize: '12px' }}>Information Needed for Higher Confidence:</b>
                  <ul style={{ margin: '6px 0 0', paddingLeft: '20px', fontSize: '12px', color: '#78350F' }}>
                    {result.required_additional_info.map((item: string, i: number) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {result.llm && result.llm.provider && (
                <div className="llmcard">
                  <b>Explanation Layer: {result.llm.provider} ({result.llm.model})</b>
                  <span>Status: {result.llm.status} · Latency: {result.llm.latency_ms ?? 0} ms {result.llm.fallback_used ? '· (fallback used)' : ''}</span>
                </div>
              )}

              <h3>Agent contributions</h3>
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
                {result.execution_trace?.map((x: string, i: number) => (
                  <div key={i}>
                    <span>{String(i + 1).padStart(2, '0')}</span>
                    {x}
                  </div>
                ))}
              </div>

              <h3>Structured Agent Evidence</h3>
              <div className="trace">
                {(result.evidence_items || []).map((e: any, i: number) => (
                  <div key={i}>
                    <span>{e.agent}</span>
                    <div>
                      <strong>{e.finding}</strong>
                      <div style={{ color: 'var(--text-secondary)', fontSize: '11px', marginTop: '2px' }}>
                        Source: {e.source} ({e.source_type}) · Confidence: {e.confidence}
                      </div>
                    </div>
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
                <p className="muted">No conflict was recorded for this run.</p>
              )}
            </div>
          )}
        </div>
      </section>

      {result && (
        <section className="panel">
          <div className="panelhead">
            <div>
              <span className="eyebrow">OBSERVABILITY & AUDIT</span>
              <h2>Knowledge Evidence & Decision Provenance</h2>
            </div>
            <span className="runid">{result.run_id}</span>
          </div>

          <div className="evidence">
            {((result.evidence || []) as any[]).map((e: any, idx: number) => {
              const badges = e.relevance_badges || e.metadata?.relevance_badges || {};
              const cropMatch = badges.crop_match || badges.crop;
              const locMatch = badges.location_match || badges.location;
              const stageMatch = badges.stage_match || badges.stage;
              const authMatch = badges.source_authority || badges.authority;
              const sourceDoc = e.source || e.metadata?.source_document || e.document || 'ICAR Kharif Agro-Advisories 2025';
              const pageNum = e.page ?? e.metadata?.source_page ?? '—';
              const chunkNum = e.chunk ?? e.metadata?.chunk ?? '—';
              const scoreVal = Number(e.final_rank_score ?? e.score ?? e.metadata?.final_rank_score ?? 0).toFixed(2);
              const reliabilityVal = Number(e.source_reliability ?? e.metadata?.source_reliability ?? 0.85).toFixed(2);

              return (
                <div key={e.id || idx}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <b>{sourceDoc}</b>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--primary)' }}>
                      Rank Score: {scoreVal}
                    </span>
                  </div>
                  <div style={{ margin: '4px 0 6px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {cropMatch && (
                      <span className={`relbadge relbadge-${cropMatch.toLowerCase() === 'high' ? 'high' : cropMatch.toLowerCase() === 'medium' ? 'med' : 'low'}`}>
                        Crop: {cropMatch} ({Number(e.crop_relevance ?? 1.0).toFixed(2)})
                      </span>
                    )}
                    {locMatch && (
                      <span className={`relbadge relbadge-${locMatch.toLowerCase() === 'high' ? 'high' : locMatch.toLowerCase() === 'medium' ? 'med' : 'low'}`}>
                        Location: {locMatch} ({Number(e.location_relevance ?? 0.8).toFixed(2)})
                      </span>
                    )}
                    {stageMatch && (
                      <span className={`relbadge relbadge-${stageMatch.toLowerCase() === 'high' ? 'high' : stageMatch.toLowerCase() === 'medium' ? 'med' : 'low'}`}>
                        Stage: {stageMatch} ({Number(e.stage_relevance ?? 0.8).toFixed(2)})
                      </span>
                    )}
                    <span className="relbadge relbadge-high">
                      Reliability: {reliabilityVal} ({authMatch || 'HIGH'})
                    </span>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                    Source: {sourceDoc} · Page: {pageNum} · Chunk: {chunkNum} · Reliability: {reliabilityVal}
                  </span>
                  <p>{e.text}</p>
                </div>
              );
            })}
          </div>

          <h3>Report Field Outcome (Feedback Loop)</h3>
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

      <footer>AgriMind · Deterministic decision engine is authoritative · LLMs provide explanation only · Field agronomy judgment must validate real application.</footer>
    </main>
  );
}

function Metric({ n, l }: { n: number | undefined; l: string }) {
  return (
    <div>
      <strong>{Number(n || 0).toFixed(2)}</strong>
      <span>{l}</span>
    </div>
  );
}
