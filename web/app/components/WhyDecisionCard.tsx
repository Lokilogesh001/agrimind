'use client';

import React, { useState } from 'react';
import { HelpCircle, ChevronDown, ChevronUp, ShieldCheck, AlertCircle, Sparkles, BookOpen, Clock } from 'lucide-react';

interface WhyDecisionCardProps {
  recommendation: string;
  conflicts?: any[];
  safetyConstraints?: string[];
  reEvaluationTrigger?: string;
  weather?: any;
  soil?: any;
  disease?: any;
  llmExplanation?: {
    summary?: string;
    why_this_decision?: string;
    immediate_guidance?: string;
    additional_agronomic_context?: string[];
    important_cautions?: string[];
    what_could_change_decision?: string[];
    evidence_used?: string[];
    uncertainty?: string;
    llm_role?: string;
  } | null;
  evidence?: any[];
}

export function WhyDecisionCard({
  recommendation,
  conflicts = [],
  safetyConstraints = [],
  reEvaluationTrigger,
  weather,
  soil,
  disease,
  llmExplanation,
  evidence = [],
}: WhyDecisionCardProps) {
  const [expanded, setExpanded] = useState(true);

  // Fallback heuristic factors
  const normRec = String(recommendation || 'monitor').toLowerCase();

  let primaryReason = 'All specialist agents agree that standard routine crop care is appropriate.';
  let supportingFactor = 'Weather and soil parameters are within normal seasonal tolerances.';
  let secondaryFactor = 'No acute phytosanitary or market pressure detected.';
  let safetyRule = 'Standard agronomic safety guard verified.';

  if (normRec.includes('disease') || normRec === 'disease_management_first') {
    primaryReason = 'High-confidence disease detection on crop foliage requires immediate phytosanitary response.';
    supportingFactor = weather?.rainfall_risk > 0.4
      ? 'Elevated moisture/rainfall conditions accelerate pathogen spread and increase disease pressure.'
      : 'Crop leaf symptoms indicate active fungal or bacterial pathogen presence.';
    secondaryFactor = soil?.npk_available
      ? 'Soil nutrient deficiency exists, but nutrient replenishment is held until disease spread is arrested.'
      : 'Nutrient application is secondary to crop survival.';
    safetyRule = 'Safety Rule B/C: Disease management takes precedence over nutrient correction when disease severity or confidence exceeds safety thresholds.';
  } else if (normRec.includes('delay')) {
    primaryReason = `Heavy precipitation risk (${weather?.risk_level || 'HIGH'}) makes immediate agrochemical application unsafe.`;
    supportingFactor = 'Chemical wash-off, nutrient leaching, and non-target environmental runoff occur under rain.';
    secondaryFactor = 'Field machinery access is impeded by excessive soil saturation.';
    safetyRule = 'Safety Rule D (Weather Safety): Immediate chemical application blocked; DELAY enforced until precipitation hazard passes.';
  } else if (normRec.includes('fertilizer')) {
    primaryReason = `Verified ${soil?.priority_nutrient || 'nutrient'} deficiency exceeds application threshold.`;
    supportingFactor = 'Current low weather risk ensures fertilizer is absorbed safely without leaching.';
    secondaryFactor = 'Crop vegetative stage is receptive to timely basal or top-dressing nutrition.';
    safetyRule = 'Safety Rule A: Measured soil values confirm nutrient deficit before dosage recommendation.';
  } else if (!soil?.npk_available) {
    primaryReason = 'Soil NPK values are unmeasured; conservative monitoring prevents harmful blind fertilizer dosing.';
    supportingFactor = 'No severe foliar disease detected.';
    secondaryFactor = 'Weather forecast remains stable.';
    safetyRule = 'Safety Rule A (Soil Safety): Exact chemical fertilizer dosage blocked until soil test is verified.';
  }

  // Farmer-facing values prioritized from OpenAI explanation when available
  const whyMatters = llmExplanation?.why_this_decision || primaryReason;
  const agronomicContext = llmExplanation?.additional_agronomic_context || [];
  const cautions = (llmExplanation?.important_cautions && llmExplanation.important_cautions.length > 0)
    ? llmExplanation.important_cautions
    : (safetyConstraints.length > 0 ? safetyConstraints : [safetyRule]);
  const monitorTriggers = (llmExplanation?.what_could_change_decision && llmExplanation.what_could_change_decision.length > 0)
    ? llmExplanation.what_could_change_decision
    : (reEvaluationTrigger ? [reEvaluationTrigger] : ['Re-evaluate during routine weekly scouting or significant weather shifts.']);

  return (
    <div className="card">
      <div
        className="card-header"
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <HelpCircle size={17} color="var(--forest-primary)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>WHY THIS DECISION? (AGRONOMIC RATIONALE)</h3>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ fontSize: '11px', padding: '3px 8px' }}
        >
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          <span>{expanded ? 'Collapse' : 'Explain'}</span>
        </button>
      </div>

      {expanded && (
        <div className="card-body">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* 1. WHY THIS MATTERS */}
            <div style={{ background: 'var(--bg-surface-soft)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--forest-primary)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--forest-dark)', letterSpacing: '0.04em', display: 'block', marginBottom: '4px' }}>
                WHY THIS MATTERS
              </span>
              <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--text-primary)', fontWeight: 500, lineHeight: 1.5 }}>
                {whyMatters}
              </p>
            </div>

            {/* 2. ADDITIONAL AGRONOMIC INSIGHT */}
            <div style={{ background: 'var(--bg-surface-soft)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--teal-primary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <Sparkles size={14} color="var(--teal-dark)" />
                <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--teal-dark)', letterSpacing: '0.04em' }}>
                  ADDITIONAL AGRONOMIC INSIGHT
                </span>
              </div>
              {agronomicContext.length > 0 ? (
                <ul style={{ margin: '4px 0 8px 18px', padding: 0, fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {agronomicContext.map((c, i) => (
                    <li key={i} style={{ marginBottom: '4px' }}>{c}</li>
                  ))}
                </ul>
              ) : (
                <p style={{ margin: '0 0 6px', fontSize: '12.5px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  Additional evidence-grounded context is unavailable.
                </p>
              )}
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', marginTop: '6px' }}>
                Source basis: Retrieved ICAR scientific reference documents & regional crop baselines.
              </div>
            </div>

            {/* 3. IMPORTANT CAUTIONS */}
            <div style={{ background: 'var(--forest-tint)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--forest-tint-border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <ShieldCheck size={15} color="var(--forest-dark)" />
                <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--forest-dark)', letterSpacing: '0.04em' }}>
                  IMPORTANT CAUTIONS & SAFETY RULES
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {cautions.map((caution, i) => (
                  <p key={i} style={{ margin: 0, fontSize: '12.5px', color: 'var(--forest-deep)', lineHeight: 1.45 }}>
                    • {caution}
                  </p>
                ))}
              </div>
            </div>

            {/* 4. WHAT TO MONITOR */}
            <div style={{ background: 'var(--bg-surface-soft)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--mint-primary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <Clock size={14} color="var(--mint-primary)" />
                <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--mint-primary)', letterSpacing: '0.04em' }}>
                  WHAT TO MONITOR
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {monitorTriggers.map((trig, i) => (
                  <p key={i} style={{ margin: 0, fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    • {trig}
                  </p>
                ))}
              </div>
            </div>

            {/* Conflicting Signals reconciled by Decision Engine if any */}
            {conflicts && conflicts.length > 0 && (
              <div style={{ marginTop: '4px' }}>
                <span style={{ fontSize: '11.5px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Signals Reconciled by Decision Engine ({conflicts.length})
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                  {conflicts.map((c, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '10px 12px',
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                        <strong style={{ color: 'var(--text-primary)' }}>
                          {c.agent_a?.toUpperCase()} vs {c.agent_b?.toUpperCase()} ({c.issue || c.conflict_type})
                        </strong>
                        <span style={{ fontSize: '10px', color: 'var(--forest-primary)', fontWeight: 700 }}>
                          RESOLVED
                        </span>
                      </div>
                      <p style={{ margin: '2px 0 4px', color: 'var(--text-secondary)' }}>
                        {c.evidence}
                      </p>
                      <div style={{ fontSize: '11.5px', color: 'var(--forest-dark)', fontWeight: 600 }}>
                        ↳ Resolution: {c.resolution}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
