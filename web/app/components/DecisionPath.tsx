'use client';

import React, { useState } from 'react';
import { GitMerge, ChevronDown, ChevronUp, CheckCircle2, ShieldCheck, ArrowDown } from 'lucide-react';

interface DecisionPathProps {
  crop?: string;
  location?: string;
  recommendation: string;
  weather?: any;
  soil?: any;
  disease?: any;
  market?: any;
  conflicts?: any[];
  safetyConstraints?: string[];
}

export function DecisionPath({
  crop = 'Crop',
  location = 'Field Location',
  recommendation,
  weather,
  soil,
  disease,
  market,
  conflicts = [],
  safetyConstraints = [],
}: DecisionPathProps) {
  const [expanded, setExpanded] = useState(false);

  // Summarize Specialist Findings
  const weatherFinding = weather?.is_available !== false && weather?.status !== 'UNAVAILABLE'
    ? `Rainfall risk: ${Number(weather?.rainfall_risk || 0).toFixed(2)} (${weather?.risk_level || 'LOW'})`
    : 'Weather telemetry unavailable; conservative neutral safety assumed';

  const soilFinding = soil?.npk_available
    ? `Nutrient deficiency: ${Number(soil?.overall_deficiency || 0).toFixed(2)} (${soil?.priority_nutrient || 'balanced'})`
    : 'NPK unmeasured; chemical fertilizer dosing safely blocked';

  const diseaseFinding = disease?.predicted_class
    ? (disease.crop_mismatch
      ? `Crop mismatch: Selected ${crop}, detected ${disease.crop_detected || 'other'}`
      : `${disease.predicted_class.replace(/___/g, ' ')} (${Math.round((disease.confidence || 0) * 100)}% conf)`)
    : 'No leaf image provided; foliar disease diagnosis inactive';

  const marketFinding = market?.is_available !== false && market?.status !== 'UNAVAILABLE'
    ? `Signal: ${(market?.signal || 'hold').toUpperCase()} (score ${Number(market?.market_score || 0).toFixed(2)})`
    : 'Market signal: hold (offline fallback)';

  const safetyGuardSummary = safetyConstraints && safetyConstraints.length > 0
    ? safetyConstraints[0]
    : 'Deterministic agronomic safety constraints verified.';

  return (
    <div className="card">
      <div
        className="card-header"
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GitMerge size={17} color="var(--forest-primary)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>HOW AGRIMIND REACHED THIS DECISION</h3>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ fontSize: '11px', padding: '3px 8px' }}
        >
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          <span>{expanded ? 'Hide Trace' : 'View Decision Flow'}</span>
        </button>
      </div>

      <div className="card-body">
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
          Visual trace of the multi-agent decision pipeline from raw field inputs through safety guards to final advisory:
        </p>

        <div className="decision-path-flow">
          {/* Node 1: Farm Inputs */}
          <div className="flow-step-row">
            <div className="flow-step-num">1</div>
            <div className="flow-step-content">
              <div className="flow-step-title">
                <span>Field Context Ingestion</span>
                <span className="badge badge-neutral" style={{ fontSize: '10px' }}>Input Layer</span>
              </div>
              <div className="flow-step-desc">
                Ingested farm location (<strong>{location}</strong>), target crop (<strong>{crop}</strong>), and field parameters.
              </div>
            </div>
          </div>

          {/* Node 2: Specialist Analyses */}
          <div className="flow-step-row">
            <div className="flow-step-num">2</div>
            <div className="flow-step-content">
              <div className="flow-step-title">
                <span>Specialist Agent Evidence Extraction</span>
                <span className="badge badge-brand" style={{ fontSize: '10px' }}>4 Agents</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '6px', marginTop: '6px', fontSize: '11.5px' }}>
                <div style={{ background: 'var(--bg-surface)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                  <strong>Weather Agent:</strong> {weatherFinding}
                </div>
                <div style={{ background: 'var(--bg-surface)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                  <strong>Soil Agent:</strong> {soilFinding}
                </div>
                <div style={{ background: 'var(--bg-surface)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                  <strong>Disease Agent:</strong> {diseaseFinding}
                </div>
                <div style={{ background: 'var(--bg-surface)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                  <strong>Market Agent:</strong> {marketFinding}
                </div>
              </div>
            </div>
          </div>

          {/* Node 3: Conflict Detection */}
          <div className="flow-step-row">
            <div className="flow-step-num">3</div>
            <div className="flow-step-content">
              <div className="flow-step-title">
                <span>Conflict Resolution & Priority Hierarchy</span>
                <span className="badge badge-warning" style={{ fontSize: '10px' }}>
                  {conflicts?.length ? `${conflicts.length} Reconciled` : 'No Conflicts'}
                </span>
              </div>
              <div className="flow-step-desc">
                {conflicts?.length ? (
                  <span>
                    Reconciled {conflicts.length} competing signals (e.g. {conflicts[0]?.issue || 'agronomic priorities'}) using deterministic conflict policy.
                  </span>
                ) : (
                  <span>Specialist agent signals are aligned; standard weighted scoring executed.</span>
                )}
              </div>
            </div>
          </div>

          {/* Node 4: Safety Guard */}
          <div className="flow-step-row">
            <div className="flow-step-num">4</div>
            <div className="flow-step-content" style={{ borderLeft: '3px solid var(--forest-primary)' }}>
              <div className="flow-step-title">
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <ShieldCheck size={14} color="var(--forest-dark)" />
                  Deterministic Agronomic Safety Guard
                </span>
                <span className="badge badge-success" style={{ fontSize: '10px' }}>Guarded</span>
              </div>
              <div className="flow-step-desc" style={{ color: 'var(--forest-deep)', fontWeight: 500 }}>
                {safetyGuardSummary}
              </div>
            </div>
          </div>

          {/* Node 5: Final Decision */}
          <div className="flow-step-row">
            <div className="flow-step-num" style={{ background: 'var(--forest-dark)', color: '#fff', borderColor: 'var(--forest-deep)' }}>
              5
            </div>
            <div className="flow-step-content" style={{ background: 'var(--forest-tint)', borderColor: 'var(--forest-tint-border)' }}>
              <div className="flow-step-title">
                <span style={{ color: 'var(--forest-deep)', fontWeight: 800 }}>
                  Authoritative Final Recommendation
                </span>
                <span className="badge badge-brand" style={{ fontSize: '11px' }}>Authoritative</span>
              </div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--forest-dark)', marginTop: '2px' }}>
                {String(recommendation).replace(/_/g, ' ').toUpperCase()}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
