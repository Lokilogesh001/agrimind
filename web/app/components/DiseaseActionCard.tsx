'use client';

import React from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  FileCheck,
  CheckCircle2,
  Clock,
  CloudRain,
  BookOpen,
  AlertCircle,
} from 'lucide-react';
import { StatusBadge } from './StatusBadge';

export interface TreatmentDetails {
  crop?: string;
  disease_name?: string;
  active_ingredient?: string;
  formulation?: string;
  dosage?: string;
  water_volume_per_acre?: string;
  pre_harvest_interval_days?: number;
  re_entry_interval_hours?: number;
  ppe_requirements?: string[];
  rainfastness_window_hours?: number;
  registration_status?: string;
  authoritative_source?: string;
  application_notes?: string;
}

export interface TreatmentPermissionData {
  status?: string;
  is_permitted?: boolean;
  action_instruction?: string;
  weather_hold?: boolean;
  rain_free_window_hours?: number;
  reassessment_trigger?: string;
  cultural_measures?: string;
  safety_disclaimer?: string;
  authority_reference?: string;
  treatment_details?: TreatmentDetails | null;
}

interface DiseaseActionCardProps {
  disease?: {
    predicted_class?: string | null;
    confidence?: number;
    classifier_score?: number;
    severity?: string;
    severity_qualification?: string;
    actionable?: boolean;
    crop_mismatch?: boolean;
    crop_detected?: string;
    normalized_disease?: string;
    block_reason?: string;
    status?: string;
    model_architecture?: string;
    model_version?: string;
    crop_concordance?: number | null;
    crop_aware_mode?: boolean;
    ambiguous?: boolean;
    recommendation_note?: string | null;
    top_alternatives?: Array<{ class: string; confidence?: number; conditioned_confidence?: number; flat_confidence?: number }>;
  } | null;
  crop?: string;
  evidenceText?: string;
  treatmentPermission?: TreatmentPermissionData | null;
  recommendation?: string;
}

export function DiseaseActionCard({
  disease,
  crop = 'Crop',
  evidenceText,
  treatmentPermission,
  recommendation,
}: DiseaseActionCardProps) {
  if (!disease || !disease.predicted_class) {
    return (
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>DISEASE MANAGEMENT</h3>
          </div>
          <StatusBadge label="NO DISEASE DETECTED" variant="success" icon="shield-check" size="sm" />
        </div>
        <div className="card-body">
          <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--text-secondary)' }}>
            No significant foliar disease detected from the submitted image or field context. Continue regular preventive monitoring and field sanitation.
          </p>
        </div>
      </div>
    );
  }

  const isHealthy = disease.predicted_class.toLowerCase().includes('healthy');
  if (isHealthy) {
    return (
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={18} color="var(--semantic-success)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>DISEASE MANAGEMENT</h3>
          </div>
          <StatusBadge label="HEALTHY CROP" variant="success" icon="shield-check" size="sm" />
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <CheckCircle2 size={22} color="var(--semantic-success)" style={{ flexShrink: 0 }} />
            <div>
              <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                Foliage Appears Healthy
              </strong>
              <p style={{ margin: '3px 0 0', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Visual classification indicates healthy leaf tissue. No chemical fungicides or phytosanitary treatments are required.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const confidence = disease.confidence ?? disease.classifier_score ?? 0;
  const confPercent = Math.round(confidence * 100);
  const isLowConfidence = confidence < 0.60;
  const isMismatch = Boolean(disease.crop_mismatch);
  const isActionable = Boolean(disease.actionable);

  const perm = treatmentPermission || {};
  const isWeatherHold = Boolean(
    perm.weather_hold ||
    perm.status === 'DEFERRED_WEATHER' ||
    (recommendation && recommendation.toLowerCase().includes('delay'))
  );
  const isPermitted = Boolean(perm.is_permitted && !isWeatherHold);
  const details = perm.treatment_details;

  const cleanName = disease.predicted_class
    .replace(/___/g, ' ')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());

  // Determine badge styling based on permission state
  let badgeLabel = 'ACTION ALLOWED';
  let badgeVariant: 'danger' | 'warning' | 'success' | 'neutral' = 'danger';
  if (isMismatch) {
    badgeLabel = 'ACTION BLOCKED · MISMATCH';
    badgeVariant = 'danger';
  } else if (isLowConfidence) {
    badgeLabel = 'UNVERIFIED DIAGNOSIS';
    badgeVariant = 'warning';
  } else if (isWeatherHold) {
    badgeLabel = 'SPRAY DEFERRED · WEATHER';
    badgeVariant = 'warning';
  } else if (isPermitted) {
    badgeLabel = 'TREATMENT PERMITTED';
    badgeVariant = 'success';
  }

  return (
    <div
      className="card"
      style={{
        borderLeft: `4px solid ${isWeatherHold ? 'var(--semantic-warning)' : isMismatch ? 'var(--semantic-danger)' : 'var(--forest-dark)'}`,
      }}
    >
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert
            size={18}
            color={isWeatherHold ? 'var(--semantic-warning)' : isMismatch ? 'var(--semantic-danger)' : 'var(--forest-dark)'}
          />
          <h3 style={{ fontSize: '15px', margin: 0 }}>DISEASE MANAGEMENT & VERIFIED TREATMENT</h3>
        </div>
        <StatusBadge
          label={badgeLabel}
          variant={badgeVariant}
          icon={isWeatherHold ? 'warning' : isMismatch ? 'danger' : 'shield-check'}
          size="sm"
        />
      </div>

      <div className="card-body">
        {/* Weather Hold / Rainfall Veto Banner */}
        {isWeatherHold && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--semantic-warning-bg)',
              border: '1px solid var(--semantic-warning-border)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
            }}
          >
            <CloudRain size={22} color="var(--semantic-warning-text)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ fontSize: '13.5px', color: 'var(--semantic-warning-text)' }}>
                CHEMICAL SPRAYING TEMPORARILY DEFERRED · HIGH RAINFALL RISK
              </strong>
              <p style={{ margin: '4px 0 0', fontSize: '12.5px', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                {perm.action_instruction ||
                  'Foliar spraying is suspended due to imminent rainfall. Applying chemicals in wet conditions causes pesticide wash-off, zero biological efficacy, and environmental runoff into water bodies.'}
              </p>
              <div style={{ marginTop: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--semantic-warning-text)' }}>
                Required Rain-Free Window: {perm.rain_free_window_hours || 24} hours prior to application.
              </div>
            </div>
          </div>
        )}

        {/* Low Confidence Warning Banner */}
        {isLowConfidence && !isMismatch && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--semantic-warning-bg)',
              border: '1px solid var(--semantic-warning-border)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
            }}
          >
            <AlertTriangle size={20} color="var(--semantic-warning-text)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ fontSize: '13px', color: 'var(--semantic-warning-text)' }}>
                LOW CONFIDENCE DIAGNOSIS ({confPercent}%)
              </strong>
              <p style={{ margin: '3px 0 0', fontSize: '12.5px', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                Visual classifier score is below the 60% policy threshold. Chemical treatments are strictly prohibited pending in-person leaf inspection by an agronomist or local KVK.
              </p>
            </div>
          </div>
        )}

        {/* Crop Mismatch Banner */}
        {isMismatch && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--semantic-danger-bg)',
              border: '1px solid var(--semantic-danger-border)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
            }}
          >
            <AlertTriangle size={20} color="var(--semantic-danger-text)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ fontSize: '13px', color: 'var(--semantic-danger-text)' }}>
                CROP MISMATCH GUARD ACTIVATED
              </strong>
              <p style={{ margin: '3px 0 0', fontSize: '12.5px', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                Selected crop is <strong>{crop}</strong>, but leaf model detected characteristics of <strong>{disease.crop_detected || 'another crop'}</strong>. Chemical action is blocked to avoid off-label phytotoxicity.
              </p>
            </div>
          </div>
        )}

        {/* Diagnosis Header Details Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '12px',
            marginBottom: '16px',
            background: 'var(--bg-surface-soft)',
            padding: '12px 16px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Detected Pathogen
            </span>
            <div style={{ fontSize: '13.5px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {details?.disease_name || cleanName}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Classifier Score
            </span>
            <div style={{ fontSize: '13.5px', fontWeight: 700, color: isLowConfidence ? 'var(--semantic-warning-text)' : 'var(--text-primary)', marginTop: '2px' }}>
              {confPercent}%
              <span style={{ fontSize: '10.5px', fontWeight: 400, color: 'var(--text-muted)', display: 'block' }}>
                {disease.model_architecture || 'MobileNetV3-Large'} {disease.model_version ? `(${disease.model_version})` : ''}
              </span>
            </div>
          </div>

          <div>
            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Canopy Symptom Priority
            </span>
            <div style={{ fontSize: '13.5px', fontWeight: 700, textTransform: 'capitalize', color: disease.severity === 'high' ? 'var(--semantic-danger-text)' : 'var(--text-primary)', marginTop: '2px' }}>
              {disease.severity || 'Moderate'}
              <span style={{ fontSize: '10.5px', fontWeight: 400, color: 'var(--text-muted)', display: 'block' }}>
                Virulence heuristic
              </span>
            </div>
          </div>

          <div>
            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Spraying State
            </span>
            <div
              style={{
                fontSize: '13.5px',
                fontWeight: 700,
                color: isWeatherHold ? 'var(--semantic-warning-text)' : isPermitted ? 'var(--semantic-success-text)' : 'var(--semantic-danger-text)',
                marginTop: '2px',
              }}
            >
              {isWeatherHold ? 'HOLD (WEATHER)' : isPermitted ? 'PERMITTED' : 'RESTRICTED'}
              <span style={{ fontSize: '10.5px', fontWeight: 400, color: 'var(--text-muted)', display: 'block' }}>
                {isWeatherHold ? 'Rainfall veto active' : isPermitted ? 'Conditions cleared' : 'Safety blocked'}
              </span>
            </div>
          </div>
        </div>

        {/* Ambiguous or Low Confidence Field Confirmation Advice */}
        {(disease.ambiguous || disease.recommendation_note) && !isMismatch && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-surface-soft)',
              border: '1px solid var(--border-color)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
            }}
          >
            <AlertCircle size={16} color="var(--forest-dark)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <strong style={{ color: 'var(--text-primary)' }}>Diagnostic Confirmation Guidance: </strong>
              {disease.recommendation_note ||
                'Visual symptoms are close to decision boundaries. Inspect under diffuse natural sunlight, examine lower leaf surfaces for fungal sporulation, and consult your regional agricultural extension officer before initiating chemical spraying.'}
            </div>
          </div>
        )}

        {/* Crop Concordance Metric */}
        {disease.crop_concordance !== null && disease.crop_concordance !== undefined && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-surface-soft)',
              border: '1px solid var(--border-subtle)',
              marginBottom: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '12px',
            }}
          >
            <span style={{ color: 'var(--text-secondary)' }}>
              <strong>Crop Concordance Metric:</strong> {(disease.crop_concordance * 100).toFixed(1)}% probability alignment with entered crop ({crop})
            </span>
            <span style={{ fontWeight: 600, color: disease.crop_concordance >= 0.15 ? 'var(--forest-dark)' : 'var(--semantic-warning-text)' }}>
              {disease.crop_concordance >= 0.15 ? '✓ Concordant' : '⚠ Low Concordance'}
            </span>
          </div>
        )}

        {/* Explicit Disclosure for Crop-Aware Constraint */}
        {disease.crop_aware_mode && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-surface-soft)',
              border: '1px solid var(--border-subtle)',
              marginBottom: '16px',
              fontSize: '11.5px',
              color: 'var(--text-secondary)',
              lineHeight: 1.45,
            }}
          >
            <strong>Crop Constraint Disclosure:</strong> Vision probabilities were conditioned on user-specified crop ({crop}). User crop entry serves as contextual metadata and does not independently prove botanical identity.
          </div>
        )}

        {/* Top Alternative Diagnoses */}
        {disease.top_alternatives && disease.top_alternatives.length > 1 && (
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
              Differential Diagnoses (Top Alternative Candidate Pathogens)
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {disease.top_alternatives.slice(0, 4).map((alt, idx) => {
                const altConfidence = alt.confidence ?? alt.conditioned_confidence ?? alt.flat_confidence ?? 0;
                const altPct = Math.round(altConfidence * 100);
                const altName = alt.class.replace(/___/g, ' ').replace(/_/g, ' ');
                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: idx === 0 ? 'var(--forest-tint)' : 'var(--bg-surface-soft)',
                      border: `1px solid ${idx === 0 ? 'var(--forest-tint-border)' : 'var(--border-subtle)'}`,
                      borderRadius: 'var(--radius-xs)',
                      padding: '7px 12px',
                      fontSize: '12px',
                    }}
                  >
                    <span style={{ fontWeight: idx === 0 ? 600 : 400, color: 'var(--text-primary)' }}>
                      {idx + 1}. {altName}
                    </span>
                    <span style={{ fontWeight: 600, color: idx === 0 ? 'var(--forest-dark)' : 'var(--text-muted)' }}>
                      {altPct}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Immediate Cultural & Field Sanitation Actions */}
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ fontSize: '13px', color: 'var(--forest-dark)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={16} color="var(--forest-dark)" />
            Immediate Cultural Sanitation & Phytosanitary Measures:
          </h4>
          <p
            style={{
              margin: 0,
              fontSize: '13px',
              color: 'var(--text-primary)',
              lineHeight: 1.55,
              background: 'var(--bg-surface-soft)',
              padding: '12px 14px',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            {perm.cultural_measures ||
              'Inspect foliage immediately. Remove and destroy severely infected plant debris. Prune lower canopy leaves for aeration. Avoid overhead sprinkler irrigation.'}
          </p>
        </div>

        {/* Verified Chemical Treatment Specifications */}
        {details && (
          <div
            style={{
              marginBottom: '16px',
              padding: '14px 16px',
              background: isWeatherHold ? 'var(--bg-surface-soft)' : 'var(--forest-tint)',
              border: `1px solid ${isWeatherHold ? 'var(--border-color)' : 'var(--forest-tint-border)'}`,
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--forest-dark)', letterSpacing: '0.04em' }}>
                {isWeatherHold ? 'STANDBY REGISTERED FORMULATION (APPLY POST-RAIN)' : 'VERIFIED RECOMMENDED TREATMENT FORMULATION'}
              </span>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                {details.registration_status}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '12px' }}>
              <div>
                <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block' }}>
                  Formulation
                </span>
                <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                  {details.formulation}
                </strong>
              </div>

              <div>
                <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block' }}>
                  Mixing Dosage
                </span>
                <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                  {details.dosage}
                </strong>
              </div>

              <div>
                <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block' }}>
                  Water Volume
                </span>
                <span style={{ fontSize: '12.5px', color: 'var(--text-primary)', fontWeight: 600 }}>
                  {details.water_volume_per_acre} / acre
                </span>
              </div>

              <div>
                <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block' }}>
                  Safety Intervals
                </span>
                <span style={{ fontSize: '12.5px', color: 'var(--text-primary)', fontWeight: 600 }}>
                  PHI: {details.pre_harvest_interval_days} days · REI: {details.re_entry_interval_hours}h
                </span>
              </div>
            </div>

            {/* Application Notes */}
            <p style={{ margin: '0 0 8px', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <strong>Application Protocol:</strong> {details.application_notes}
            </p>

            {/* PPE Required */}
            {details.ppe_requirements && (
              <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                <strong style={{ color: 'var(--text-primary)' }}>Mandatory PPE:</strong> {details.ppe_requirements.join(', ')}
              </div>
            )}
          </div>
        )}

        {/* Unregistered or Extension Referral State */}
        {!details && isActionable && !isMismatch && (
          <div
            style={{
              marginBottom: '16px',
              padding: '14px 16px',
              background: 'var(--bg-surface-soft)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <BookOpen size={16} color="var(--forest-dark)" />
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                State Agricultural Extension Consultation Required
              </strong>
            </div>
            <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              AgriMind enforces strict pesticide validation and does not guess chemical doses for non-cataloged combinations. Please visit your district Krishi Vigyan Kendra (KVK) or contact the Kisan Call Centre (Toll-Free 1800-180-1551) for registered recommendations.
            </p>
          </div>
        )}

        {/* Safety & Compliance Statutory Footer */}
        <div
          style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            background: 'var(--bg-surface-soft)',
            padding: '10px 14px',
            borderRadius: 'var(--radius-xs)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
          }}
        >
          <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '1px' }} />
          <span>
            <strong>Statutory Safety Compliance:</strong> {perm.safety_disclaimer ||
              'Always follow statutory pesticide label instructions and safety intervals (PHI/REI). Never apply agrochemicals without verifying local agricultural department registration.'}
            {details?.authoritative_source && ` (Source: ${details.authoritative_source})`}
          </span>
        </div>
      </div>
    </div>
  );
}
