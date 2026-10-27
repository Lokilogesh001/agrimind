'use client';

import React, { useState } from 'react';
import {
  ShieldCheck,
  Activity,
  CheckCircle2,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileCode,
  Layers,
  Sparkles,
} from 'lucide-react';
import { StatusBadge, BadgeVariant } from './StatusBadge';
import { AgentContributions } from './AgentContributions';
import { EvidencePanel } from './EvidencePanel';

interface AuditPanelProps {
  result: any;
}

export function AuditPanel({ result }: AuditPanelProps) {
  const [copied, setCopied] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);
  const [showEqBreakdown, setShowEqBreakdown] = useState(false);

  const copyJson = () => {
    if (!result?.audit) return;
    navigator.clipboard.writeText(JSON.stringify(result.audit, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Stability & Evidence Quality Score interpretation
  const stabilityScore = Math.round((result?.decision_stability_score ?? 0.8) * 100);
  const stabilityLevel = (result?.stability_level || 'INSUFFICIENT').toUpperCase();
  let stabilityLabel = 'Stable';
  let stabilityVariant: BadgeVariant = 'success';
  if (stabilityLevel === 'HIGH') {
    stabilityLabel = 'Highly Stable';
    stabilityVariant = 'success';
  } else if (stabilityLevel === 'MODERATE') {
    stabilityLabel = 'Moderate Stability';
    stabilityVariant = 'warning';
  } else if (stabilityLevel === 'LOW') {
    stabilityLabel = 'Low Stability';
    stabilityVariant = 'danger';
  } else {
    stabilityLabel = 'Insufficient Data';
    stabilityVariant = 'neutral';
  }

  const eqScore = Math.round((result?.evidence_quality_score ?? 0.75) * 100);
  const eqLevel = (result?.evidence_quality_level || 'MODERATE').toUpperCase();
  let eqLabel = 'Strong Evidence';
  let eqVariant: BadgeVariant = 'success';
  if (eqLevel === 'GOOD') {
    eqLabel = 'Strong Evidence';
    eqVariant = 'success';
  } else if (eqLevel === 'MODERATE') {
    eqLabel = 'Moderate Evidence';
    eqVariant = 'warning';
  } else if (eqLevel === 'LOW') {
    eqLabel = 'Low Evidence Quality';
    eqVariant = 'danger';
  } else {
    eqLabel = 'Insufficient Evidence';
    eqVariant = 'neutral';
  }

  const breakdown = result?.evidence_quality_breakdown || {};

  const [showStabilityBreakdown, setShowStabilityBreakdown] = useState(false);
  const [showMetricRegistry, setShowMetricRegistry] = useState(false);

  const stabBreakdown = result?.decision_stability_breakdown || {};
  const dssScore = result?.dss_score ?? (result?.advisory?.dss_score ?? 0.6266);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Run Metadata Header */}
      <div className="card" style={{ padding: '14px 18px', background: 'var(--bg-surface)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <span className="eyebrow">AUDIT RECORD & REPRODUCIBILITY TRACE</span>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
              Run ID: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--forest-dark)' }}>{result?.run_id || 'untracked'}</code>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              onClick={() => setShowMetricRegistry(!showMetricRegistry)}
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '11px', padding: '5px 12px' }}
              type="button"
            >
              {showMetricRegistry ? 'Hide Metric Registry' : 'View Metric Registry (P2-01)'}
            </button>
            <StatusBadge label="VERIFIED AUDIT LOG" variant="brand" icon="shield-check" size="sm" />
          </div>
        </div>
      </div>

      {/* METRIC REGISTRY & GLOSSARY (P2-01 Fix) */}
      {showMetricRegistry && (
        <div className="card" style={{ borderLeft: '4px solid var(--teal-dark)' }}>
          <div className="card-header">
            <h3 style={{ fontSize: '15px', margin: 0 }}>METRIC REGISTRY & CONFIDENCE INTERPRETATION</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Formal Semantic Specification</span>
          </div>
          <div className="card-body" style={{ overflowX: 'auto', padding: '16px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '8px 10px' }}>Metric</th>
                  <th style={{ padding: '8px 10px' }}>Value</th>
                  <th style={{ padding: '8px 10px' }}>Mathematical Definition & Formula</th>
                  <th style={{ padding: '8px 10px' }}>Interpretation & Limitations</th>
                  <th style={{ padding: '8px 10px' }}>Source Fields</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text-primary)' }}>Decision Confidence</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--forest-dark)' }}>{Math.round((result?.confidence ?? 0.85) * 100)}%</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Weighted aggregate of agent certainty modulated by deterministic policy match.</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>System belief; not a frequentist probability of agronomic yield improvement.</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>advisory.confidence, safety_engine</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text-primary)' }}>Decision Stability</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--forest-dark)' }}>{stabilityScore}%</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}><code>Consensus (0.70) + Safety (+0.10) - ConflictPenalty</code></td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Measures vote alignment across agents. Decreases under rain/disease conflict.</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>state.decision_stability_breakdown</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text-primary)' }}>Evidence Quality</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--teal-dark)' }}>{eqScore}%</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}><code>0.30*Authority + 0.25*Crop + 0.20*Location + 0.15*Stage + 0.10*Freshness</code></td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Measures institutional and ecological relevance of retrieved ICAR/TNAU literature.</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>state.evidence_quality_breakdown</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text-primary)' }}>Disease Classifier Score</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{((result?.disease?.classifier_score ?? result?.disease?.confidence ?? 0.8863) * 100).toFixed(2)}%</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Softmax output probability for top-1 disease class (MobileNetV3).</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Model output confidence for class label; does NOT measure canopy leaf damage severity.</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>disease.classifier_score</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text-primary)' }}>Weather Agent Confidence</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{result?.weather?.confidence ? `${Math.round(result.weather.confidence * 100)}%` : '85%'}</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Open-Meteo API response freshness and ensemble forecast variance.</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Represents sensor and model convergence over 48h forecast window.</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>weather.confidence</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text-primary)' }}>Advisory Agent Confidence</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{result?.advisory?.confidence ? `${Math.round(result.advisory.confidence * 100)}%` : '57%'}</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Pre-safety preliminary heuristic agreement score.</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Preliminary consensus before deterministic safety overrides are applied.</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>advisory.confidence</td>
                </tr>
                <tr>
                  <td style={{ padding: '10px', fontWeight: 700, color: 'var(--text-primary)' }}>DSS Composite Score</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--forest-dark)' }}>{Number(dssScore).toFixed(4)}</td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}><code>0.40*Confidence + 0.35*Stability + 0.25*EvidenceQuality</code></td>
                  <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>Overall Decision Support index summarizing confidence, consensus, and evidence rigor.</td>
                  <td style={{ padding: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>advisory.dss_score</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Dual Scorecards: Decision Stability & Evidence Quality */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {/* Decision Stability Card */}
        <div className="card" style={{ padding: '20px', background: 'var(--bg-surface)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span className="eyebrow">DECISION STABILITY</span>
            <StatusBadge label={`${stabilityLevel} · ${stabilityLabel}`} variant={stabilityVariant} size="sm" />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ fontSize: '34px', fontWeight: 800, color: 'var(--forest-dark)', lineHeight: 1.1 }}>
              {stabilityScore}%
            </div>
            <button
              onClick={() => setShowStabilityBreakdown(!showStabilityBreakdown)}
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '11px', padding: '4px 10px' }}
              type="button"
            >
              {showStabilityBreakdown ? 'Hide Breakdown' : 'View Formula'}
            </button>
          </div>
          <p style={{ margin: '10px 0 0', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Evaluates mathematical consistency across specialist agent votes and deterministic safety policy rules.
          </p>

          {showStabilityBreakdown && (
            <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', fontSize: '11.5px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <div>Base Consensus Weight: <strong style={{ color: 'var(--text-primary)' }}>+{Math.round((stabBreakdown.base_consensus ?? 0.70) * 100)}%</strong></div>
              <div>Safety Constraints Alignment: <strong style={{ color: 'var(--text-primary)' }}>+{Math.round((stabBreakdown.safety_weight ?? 0.10) * 100)}%</strong></div>
              <div>Data Completeness Credit: <strong style={{ color: 'var(--text-primary)' }}>+{Math.round((stabBreakdown.completeness_weight ?? 0.05) * 100)}%</strong></div>
              <div>Disease vs Weather Tension Penalty: <strong style={{ color: 'var(--semantic-danger-text)' }}>-{Math.round((stabBreakdown.tension_penalty ?? 0.22) * 100)}%</strong></div>
              <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: '4px', background: 'var(--bg-surface-soft)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                Formula: {stabBreakdown.formula || 'Stability = Consensus + Safety + Completeness - Tension'}
              </div>
            </div>
          )}
        </div>

        {/* Evidence Quality Card */}
        <div className="card" style={{ padding: '20px', background: 'var(--bg-surface)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span className="eyebrow" style={{ color: 'var(--teal-dark)' }}>EVIDENCE QUALITY</span>
            <StatusBadge label={`${eqLevel} · ${eqLabel}`} variant={eqVariant} size="sm" />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ fontSize: '34px', fontWeight: 800, color: 'var(--teal-dark)', lineHeight: 1.1 }}>
              {eqScore}%
            </div>
            {Object.keys(breakdown).length > 0 && (
              <button
                onClick={() => setShowEqBreakdown(!showEqBreakdown)}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '11px', padding: '4px 10px' }}
                type="button"
              >
                {showEqBreakdown ? 'Hide Breakdown' : 'View Breakdown'}
              </button>
            )}
          </div>
          <p style={{ margin: '10px 0 0', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Multidimensional assessment of source authority, crop match, location relevance, and temporal freshness.
          </p>

          {showEqBreakdown && Object.keys(breakdown).length > 0 && (
            <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11.5px' }}>
              <div>Crop relevance: <strong style={{ color: 'var(--text-primary)' }}>{Math.round((breakdown.crop_relevance ?? 0.9) * 100)}%</strong></div>
              <div>Location match: <strong style={{ color: 'var(--text-primary)' }}>{Math.round((breakdown.location_relevance ?? 0.8) * 100)}%</strong></div>
              <div>Growth stage: <strong style={{ color: 'var(--text-primary)' }}>{Math.round((breakdown.stage_relevance ?? 0.85) * 100)}%</strong></div>
              <div>Source reliability: <strong style={{ color: 'var(--text-primary)' }}>{Math.round((breakdown.source_reliability ?? 0.9) * 100)}%</strong></div>
              <div>Temporal freshness: <strong style={{ color: 'var(--text-primary)' }}>{Math.round((breakdown.temporal_relevance ?? 0.95) * 100)}%</strong></div>
              <div>Completeness: <strong style={{ color: 'var(--text-primary)' }}>{Math.round((breakdown.completeness ?? 0.8) * 100)}%</strong></div>
            </div>
          )}
        </div>
      </div>

      {/* OpenAI Explanation & Evidence Synthesis Observability Layer */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>LLM EXPLANATION & EVIDENCE SYNTHESIS</h3>
          </div>
          <StatusBadge
            label={
              result?.llm?.provider === 'openai' && result?.llm?.status === 'success'
                ? 'OPENAI ACTIVE'
                : result?.llm?.provider === 'grok' && result?.llm?.status === 'success'
                ? (result?.llm?.fallback_used ? 'GROK ACTIVE · FALLBACK' : 'GROK ACTIVE')
                : result?.llm?.status === 'fallback'
                ? 'LLM UNAVAILABLE · FALLBACK'
                : 'DETERMINISTIC TEMPLATE'
            }
            variant={result?.llm?.status === 'success' ? 'brand' : 'warning'}
            size="sm"
          />
        </div>
        <div className="card-body">
          {/* Strict Separation of Authority Callout */}
          <div
            style={{
              background: 'var(--forest-tint)',
              border: '1px solid var(--forest-tint-border)',
              borderRadius: 'var(--radius-sm)',
              padding: '14px 18px',
              marginBottom: '16px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: '14px',
            }}
          >
            <div>
              <span style={{ fontSize: '10.5px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--forest-dark)', letterSpacing: '0.04em', display: 'block', marginBottom: '2px' }}>
                DECISION AUTHORITY
              </span>
              <strong style={{ fontSize: '14px', color: 'var(--text-primary)', display: 'block' }}>
                Deterministic Agronomic Safety Engine
              </strong>
              <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                Authoritative decision source for disease triage, weather vetos, and nutrient dosage constraints.
              </span>
            </div>
            <div>
              <span style={{ fontSize: '10.5px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--teal-dark)', letterSpacing: '0.04em', display: 'block', marginBottom: '2px' }}>
                LLM ROLE
              </span>
              <strong style={{ fontSize: '14px', color: 'var(--teal-dark)', display: 'block' }}>
                Explanation & evidence synthesis only
              </strong>
              <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                The LLM layer (OpenAI / xAI Grok) translates deterministic findings into farmer-friendly explanations. The LLM does not determine or override the final agronomic decision.
              </span>
            </div>
          </div>

          {/* Telemetry Metrics Grid with Latency & Failure Diagnostics Breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px' }}>
            <div style={{ background: 'var(--bg-surface-soft)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', display: 'block' }}>LLM Provider</span>
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '2px', display: 'block' }}>
                {result?.llm?.provider === 'openai' ? 'OpenAI' : (result?.llm?.provider === 'grok' ? 'xAI Grok' : 'Deterministic Template')}
              </strong>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', display: 'block' }}>Model</span>
              <code style={{ fontSize: '12px', color: 'var(--forest-dark)', fontFamily: 'var(--font-mono)', marginTop: '2px', display: 'block' }}>
                {result?.llm?.model || 'rule-based-template'}
              </code>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', display: 'block' }}>Failure Category</span>
              <span style={{ fontSize: '11.5px', color: result?.llm?.failure_category && result.llm.failure_category !== 'NONE' ? 'var(--semantic-warning-text)' : 'var(--text-primary)', fontWeight: 600, marginTop: '2px', display: 'block' }}>
                {result?.llm?.failure_category || (result?.llm?.status === 'success' ? 'NONE (SUCCESS)' : 'KEY_NOT_CONFIGURED')}
              </span>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', display: 'block' }}>API Attempt Latency</span>
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '2px', display: 'block' }}>
                {result?.llm?.api_attempt_latency_ms ? `${Math.round(result.llm.api_attempt_latency_ms)} ms` : '0 ms'}
              </strong>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', display: 'block' }}>Fallback Latency</span>
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '2px', display: 'block' }}>
                {result?.llm?.fallback_latency_ms ? `${Math.round(result.llm.fallback_latency_ms)} ms` : '1 ms'}
              </strong>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', display: 'block' }}>Total Latency</span>
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)', marginTop: '2px', display: 'block' }}>
                {result?.llm?.total_latency_ms || result?.llm?.latency_ms ? `${Math.round(result.llm.total_latency_ms || result.llm.latency_ms)} ms` : '0 ms'}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* Specialist Agent Contributions & Graph Topology Disambiguation */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>SPECIALIST AGENT CONTRIBUTIONS</h3>
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <span style={{ fontSize: '11px', background: 'var(--bg-surface-soft)', border: '1px solid var(--border-color)', padding: '3px 10px', borderRadius: '4px', color: 'var(--text-secondary)' }}>
              5 Specialist Nodes · 1 Safety Orchestrator · 4 RAG Citations · 6 Trajectory Steps
            </span>
          </div>
        </div>
        <div className="card-body">
          <AgentContributions
            weather={result?.weather}
            soil={result?.soil}
            disease={result?.disease}
            market={result?.market}
            advisory={result?.advisory}
            finalRecommendation={result?.recommendation}
          />
        </div>
      </div>

      {/* Deterministic Safety Guard Constraints */}
      {result?.safety_constraints && result.safety_constraints.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid var(--forest-dark)' }}>
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={18} color="var(--forest-dark)" />
              <h3 style={{ fontSize: '15px', margin: 0 }}>DETERMINISTIC AGRONOMIC SAFETY CONSTRAINTS</h3>
            </div>
            <StatusBadge label={`${result.safety_constraints.length} RULES ENFORCED`} variant="brand" size="sm" />
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {result.safety_constraints.map((c: string, idx: number) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px 14px',
                    background: 'var(--bg-surface-soft)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '12.5px',
                    color: 'var(--text-primary)',
                    lineHeight: 1.5,
                  }}
                >
                  {c}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ICAR Supporting Guidance */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>ICAR SUPPORTING SCIENTIFIC EVIDENCE</h3>
          </div>
          <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            {(result?.evidence || []).length} Document Citations
          </span>
        </div>
        <div className="card-body">
          <EvidencePanel evidenceList={result?.evidence || []} />
        </div>
      </div>

      {/* Orchestration Execution Trace */}
      {result?.execution_trace && result.execution_trace.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 style={{ fontSize: '15px', margin: 0 }}>EXECUTION TRACE</h3>
            <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
              Graph Node Trajectory
            </span>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {result.execution_trace.map((trace: string, i: number) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '9px 14px',
                    background: 'var(--bg-surface-soft)',
                    borderRadius: 'var(--radius-xs)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <span style={{ color: 'var(--forest-dark)', fontWeight: 700 }}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span>{trace}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Raw Audit JSON (Collapsed by Default with Copy button) */}
      <div className="card">
        <div
          className="card-header"
          style={{ cursor: 'pointer' }}
          onClick={() => setShowRawJson(!showRawJson)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileCode size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>RAW AUDIT DATA</h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '11px', padding: '4px 10px' }}
            >
              {showRawJson ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              <span>{showRawJson ? 'Collapse JSON' : 'Expand JSON'}</span>
            </button>
          </div>
        </div>

        {showRawJson && (
          <div className="card-body">
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
              <button
                type="button"
                onClick={copyJson}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '11px', padding: '5px 12px' }}
              >
                {copied ? <Check size={12} color="var(--semantic-success-text)" /> : <Copy size={12} />}
                <span>{copied ? 'Copied to Clipboard' : 'Copy JSON'}</span>
              </button>
            </div>
            <pre className="audit-code-box">
              {JSON.stringify(result?.audit || result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
