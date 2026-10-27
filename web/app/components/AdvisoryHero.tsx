'use client';

import React from 'react';
import {
  ShieldAlert,
  ArrowRight,
  Info,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { StatusBadge, BadgeVariant } from './StatusBadge';

interface AdvisoryHeroProps {
  recommendation: string;
  explanation: string;
  confidence?: number;
  disease?: {
    predicted_class?: string | null;
    confidence?: number;
    severity?: string;
    actionable?: boolean;
    crop_mismatch?: boolean;
    crop_detected?: string;
  } | null;
  weatherRisk?: {
    score?: number;
    level?: string;
    explanation?: string;
  } | null;
  soilStatus?: {
    npk_available?: boolean;
    overall_deficiency?: number | null;
    priority_nutrient?: string;
  } | null;
  onScrollToAction?: () => void;
}

export function AdvisoryHero({
  recommendation,
  explanation,
  confidence = 0.85,
  disease,
  weatherRisk,
  soilStatus,
  onScrollToAction,
}: AdvisoryHeroProps) {
  const normRec = String(recommendation || 'monitor').toLowerCase();

  // Determine Priority, Title, and Styling
  let priorityBadge = 'ROUTINE CARE';
  let badgeVariant: BadgeVariant = 'success';
  let cardClass = 'priority-routine';
  let heroTitle = 'Continue Routine Monitoring';
  let shortAction = 'Maintain standard cultural practices and monitor crop foliage.';

  const isDiseasePrimary = normRec.includes('disease') || normRec === 'disease_management_first';
  const isDelay = normRec.includes('delay');
  const isFertilizer = normRec.includes('apply_fertilizer') || normRec.includes('fertilizer');

  if (isDiseasePrimary) {
    priorityBadge = 'HIGH PRIORITY';
    badgeVariant = 'danger';
    cardClass = 'priority-high';
    heroTitle = 'Disease Management First';
    shortAction = 'Prioritize phytosanitary inspection and verified disease control before any fertilizer application.';
  } else if (isDelay) {
    priorityBadge = 'WEATHER CAUTION';
    badgeVariant = 'warning';
    cardClass = 'priority-warning';
    heroTitle = 'Field Applications Delayed';
    shortAction = 'Suspend all spraying and chemical top-dressing due to elevated precipitation risk.';
  } else if (isFertilizer) {
    priorityBadge = 'ACTION REQUIRED';
    badgeVariant = 'brand';
    cardClass = 'priority-routine';
    heroTitle = 'Nutrient Replenishment Recommended';
    shortAction = 'Apply scheduled fertilizer replenishment to correct verified soil deficiency.';
  } else {
    priorityBadge = 'ROUTINE CARE';
    badgeVariant = 'mint';
    cardClass = 'priority-routine';
    heroTitle = 'Routine Field Scouting & Monitoring';
    shortAction = 'No emergency intervention required. Continue regular crop management.';
  }

  // Disease info if detected
  const hasDiseaseSignal = Boolean(disease?.predicted_class && !disease.predicted_class.toLowerCase().includes('healthy'));
  const diseaseDisplayName = disease?.predicted_class
    ? disease.predicted_class.replace(/___/g, ' ').replace(/_/g, ' ')
    : '';

  const confPercent = Math.round((confidence || 0.85) * 100);

  return (
    <section className={`advisory-hero-card ${cardClass}`} aria-labelledby="advisory-heading">
      <div className="hero-body">
        {/* Top Header Row */}
        <div className="hero-header-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span className="eyebrow">
              TODAY'S ADVISORY
            </span>
            <StatusBadge
              label={priorityBadge}
              variant={badgeVariant}
              icon={isDiseasePrimary ? 'danger' : isDelay ? 'warning' : 'check'}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
              Decision Confidence:
            </span>
            <span
              style={{
                fontSize: '13px',
                fontWeight: 700,
                color: 'var(--forest-dark)',
                background: 'var(--forest-tint)',
                padding: '3px 10px',
                borderRadius: '999px',
                border: '1px solid var(--forest-tint-border)',
              }}
            >
              {confPercent}%
            </span>
          </div>
        </div>

        {/* Main Advisory Title */}
        <h2 id="advisory-heading" className="hero-main-title">
          {heroTitle}
        </h2>

        {/* Active Disease Diagnosis Banner if Present */}
        {hasDiseaseSignal && (
          <div className="hero-diagnosis-banner">
            <ShieldAlert size={22} color="var(--semantic-danger)" style={{ flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <strong style={{ fontSize: '14.5px', color: 'var(--text-primary)' }}>
                  {diseaseDisplayName}
                </strong>
                {disease?.confidence !== undefined && (
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    ({Math.round(disease.confidence * 100)}% detection confidence)
                  </span>
                )}
                <span
                  style={{
                    fontSize: '10.5px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: disease?.severity === 'high' ? 'var(--semantic-danger-bg)' : 'var(--semantic-warning-bg)',
                    border: `1px solid ${disease?.severity === 'high' ? 'var(--semantic-danger-border)' : 'var(--semantic-warning-border)'}`,
                    color: disease?.severity === 'high' ? 'var(--semantic-danger-text)' : 'var(--semantic-warning-text)',
                  }}
                >
                  {disease?.severity ? `${disease.severity} severity` : 'Detected'}
                </span>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {disease?.crop_mismatch
                  ? 'Note: Model detected potential crop mismatch. Disease action is safety-guarded.'
                  : disease?.actionable
                  ? 'Phytosanitary treatment must be prioritized over fertilizer application.'
                  : 'Prediction confidence is below actionable safety threshold; field verification recommended.'}
              </p>
            </div>
          </div>
        )}

        {/* Plain Language Advisory Explanation */}
        <p className="hero-explanation">
          {explanation}
        </p>

        {/* Action Prompt */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
          <div className="hero-action-prompt" style={{ flex: 1, minWidth: '260px' }}>
            <Info size={18} color="var(--forest-dark)" style={{ flexShrink: 0 }} />
            <span>
              <strong style={{ color: 'var(--forest-dark)' }}>Recommended Action:</strong> {shortAction}
            </span>
          </div>

          {onScrollToAction && (
            <button
              onClick={onScrollToAction}
              className="btn btn-primary btn-sm"
              style={{ whiteSpace: 'nowrap' }}
              type="button"
            >
              <span>View Action Plan</span>
              <ArrowRight size={14} />
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
