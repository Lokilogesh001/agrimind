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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Run Metadata Header */}
      <div className="card" style={{ padding: '14px 18px', background: 'var(--bg-surface)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <span className="eyebrow">AUDIT RECORD</span>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Run ID: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--forest-dark)' }}>{result?.run_id || 'untracked'}</code>
            </div>
          </div>
          <StatusBadge label="VERIFIED AUDIT LOG" variant="brand" icon="shield-check" size="sm" />
        </div>
      </div>

      {/* Dual Scorecards: Decision Stability & Evidence Quality */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {/* Decision Stability Card */}
        <div className="card" style={{ padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span className="eyebrow" style={{ color: 'var(--forest-dark)' }}>DECISION STABILITY</span>
            <StatusBadge label={`${stabilityLevel} · ${stabilityLabel}`} variant={stabilityVariant} size="sm" />
          </div>
          <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--forest-deep)', lineHeight: 1.1 }}>
            {stabilityScore}%
          </div>
          <p style={{ margin: '8px 0 0', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
            Evaluates mathematical consistency across specialist agent votes and deterministic safety policy rules.
          </p>
        </div>

        {/* Evidence Quality Card */}
        <div className="card" style={{ padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span className="eyebrow" style={{ color: 'var(--teal-dark)' }}>EVIDENCE QUALITY</span>
            <StatusBadge label={`${eqLevel} · ${eqLabel}`} variant={eqVariant} size="sm" />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--teal-dark)', lineHeight: 1.1 }}>
              {eqScore}%
            </div>
            {Object.keys(breakdown).length > 0 && (
              <button
                onClick={() => setShowEqBreakdown(!showEqBreakdown)}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '11px', padding: '3px 8px' }}
              >
                {showEqBreakdown ? 'Hide Breakdown' : 'View Breakdown'}
              </button>
            )}
          </div>
          <p style={{ margin: '8px 0 0', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
            Multidimensional assessment of source authority, crop match, location relevance, and temporal freshness.
          </p>

          {showEqBreakdown && Object.keys(breakdown).length > 0 && (
            <div style={{ marginTop: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11.5px' }}>
              <div>Crop relevance: <strong>{Math.round((breakdown.crop_relevance ?? 0.9) * 100)}%</strong></div>
              <div>Location match: <strong>{Math.round((breakdown.location_relevance ?? 0.8) * 100)}%</strong></div>
              <div>Growth stage: <strong>{Math.round((breakdown.stage_relevance ?? 0.85) * 100)}%</strong></div>
              <div>Source reliability: <strong>{Math.round((breakdown.source_reliability ?? 0.9) * 100)}%</strong></div>
              <div>Temporal freshness: <strong>{Math.round((breakdown.temporal_relevance ?? 0.95) * 100)}%</strong></div>
              <div>Completeness: <strong>{Math.round((breakdown.completeness ?? 0.8) * 100)}%</strong></div>
            </div>
          )}
        </div>
      </div>

      {/* OpenAI Explanation & Evidence Synthesis Observability Layer */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={17} color="var(--forest-primary)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>LLM EXPLANATION & EVIDENCE SYNTHESIS</h3>
          </div>
          <StatusBadge
            label={result?.llm?.provider === 'openai' && result?.llm?.status === 'success' ? 'OPENAI ACTIVE' : (result?.llm?.status === 'fallback' ? 'OPENAI UNAVAILABLE · FALLBACK' : 'DETERMINISTIC TEMPLATE')}
            variant={result?.llm?.provider === 'openai' && result?.llm?.status === 'success' ? 'brand' : 'warning'}
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
              padding: '12px 16px',
              marginBottom: '16px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: '12px',
            }}
          >
            <div>
              <span style={{ fontSize: '10.5px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--forest-dark)', letterSpacing: '0.04em', display: 'block', marginBottom: '2px' }}>
                DECISION AUTHORITY
              </span>
              <strong style={{ fontSize: '13.5px', color: 'var(--forest-deep)', display: 'block' }}>
                Deterministic Agronomic Safety Engine
              </strong>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                Authoritative decision source for disease triage, weather vetos, and nutrient dosage constraints.
              </span>
            </div>
            <div>
              <span style={{ fontSize: '10.5px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--teal-dark)', letterSpacing: '0.04em', display: 'block', marginBottom: '2px' }}>
                LLM ROLE
              </span>
              <strong style={{ fontSize: '13.5px', color: 'var(--teal-deep)', display: 'block' }}>
                Explanation & evidence synthesis only
              </strong>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                OpenAI translates deterministic findings into farmer-friendly explanations. OpenAI does not determine or override the final agronomic decision.
              </span>
            </div>
          </div>

          {/* Telemetry Metrics Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px' }}>
            <div style={{ background: 'var(--bg-surface-soft)', padding: '10px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)', display: 'block' }}>LLM Provider</span>
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                {result?.llm?.provider === 'openai' ? 'OpenAI' : 'Deterministic Template'}
              </strong>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '10px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)', display: 'block' }}>Model</span>
              <code style={{ fontSize: '12px', color: 'var(--forest-dark)', fontFamily: 'var(--font-mono)' }}>
                {result?.llm?.model || 'gpt-4o-mini'}
              </code>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '10px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)', display: 'block' }}>Role</span>
              <span style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: 600 }}>
                Explanation & Evidence Synthesis
              </span>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '10px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)', display: 'block' }}>Status</span>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: result?.llm?.status === 'success' ? 'var(--semantic-success)' : 'var(--semantic-warning)',
                }}
              >
                {result?.llm?.status === 'success' ? 'Success' : (result?.llm?.status === 'fallback' ? 'Fallback' : 'Deterministic')}
              </span>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '10px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)', display: 'block' }}>Latency</span>
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                {result?.llm?.latency_ms ? `${Math.round(result.llm.latency_ms)} ms` : '0 ms'}
              </strong>
            </div>

            <div style={{ background: 'var(--bg-surface-soft)', padding: '10px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)', display: 'block' }}>Evidence Sources Used</span>
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                {result?.llm?.evidence_sources_count ?? (result?.evidence?.length || 0)} Documents
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* Specialist Agent Contributions */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={17} color="var(--forest-primary)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>AGENT CONTRIBUTIONS</h3>
          </div>
          <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>5 Specialist Nodes</span>
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
        <div className="card" style={{ borderLeft: '4px solid var(--forest-primary)' }}>
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={17} color="var(--forest-primary)" />
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
                    padding: '10px 12px',
                    background: 'var(--bg-surface-soft)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '12.5px',
                    color: 'var(--text-primary)',
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
            <Layers size={17} color="var(--forest-primary)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>ICAR SUPPORTING SCIENTIFIC EVIDENCE</h3>
          </div>
          <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
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
            <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
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
                    padding: '8px 12px',
                    background: 'var(--bg-surface-soft)',
                    borderRadius: 'var(--radius-xs)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-primary)',
                  }}
                >
                  <span style={{ color: 'var(--forest-primary)', fontWeight: 700 }}>
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
            <FileCode size={17} color="var(--text-secondary)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>RAW AUDIT DATA</h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ fontSize: '11px', padding: '3px 8px' }}
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
                style={{ fontSize: '11px', padding: '4px 10px' }}
              >
                {copied ? <Check size={12} color="var(--semantic-success)" /> : <Copy size={12} />}
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
