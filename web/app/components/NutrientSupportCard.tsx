'use client';

import React from 'react';
import { Sprout, AlertCircle, CheckCircle2, FlaskConical, Info } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface NutrientSupportCardProps {
  soil?: {
    nutrient_status?: string;
    status?: string;
    assessment_text?: string;
    npk_available?: boolean;
    overall_deficiency?: number | null;
    priority_nutrient?: string;
    nitrogen_deficiency?: number | null;
    phosphorus_deficiency?: number | null;
    potassium_deficiency?: number | null;
    supplied?: { n?: number | null; p?: number | null; k?: number | null };
    targets?: { N?: number; P?: number; K?: number };
    soil_type?: string;
  } | null;
  crop?: string;
  growthStage?: string;
  hasActiveDisease?: boolean;
}

export function NutrientSupportCard({
  soil,
  crop = 'Crop',
  growthStage = 'Vegetative',
  hasActiveDisease = false,
}: NutrientSupportCardProps) {
  const npkAvailable = Boolean(soil?.npk_available);
  const deficiency = soil?.overall_deficiency ?? 0;
  const priorityNutrient = (soil?.priority_nutrient || '').toLowerCase();

  // If soil NPK was not measured
  if (!npkAvailable) {
    return (
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FlaskConical size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>NUTRIENT SUPPORT</h3>
          </div>
          <StatusBadge label="NPK UNMEASURED" variant="info" icon="info" size="sm" />
        </div>
        <div className="card-body">
          <div style={{ background: 'var(--semantic-info-bg)', border: '1px solid var(--semantic-info-border)', padding: '12px 16px', borderRadius: 'var(--radius-sm)', marginBottom: '14px' }}>
            <strong style={{ fontSize: '13px', color: 'var(--semantic-info-text)', display: 'block', marginBottom: '4px' }}>
              Soil Testing Required for Chemical Fertilizer Dosage
            </strong>
            <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--text-primary)', lineHeight: 1.55 }}>
              Measured NPK values were not provided for this field scenario. In accordance with agronomic safety standards, exact chemical fertilizer doses cannot be calculated safely without a verified Soil Health Card or laboratory soil analysis.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
            <Info size={16} color="var(--forest-dark)" style={{ flexShrink: 0 }} />
            <span>
              <strong style={{ color: 'var(--text-primary)' }}>Application Guidance:</strong> Exact application rate requires soil-test / local agronomist verification.
            </span>
          </div>
        </div>
      </div>
    );
  }

  // If measured, check deficiency level
  const hasDeficiency = deficiency > 0.25;

  if (!hasDeficiency) {
    return (
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FlaskConical size={18} color="var(--semantic-success)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>NUTRIENT SUPPORT</h3>
          </div>
          <StatusBadge label="BALANCED NUTRITION" variant="success" icon="check" size="sm" />
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <CheckCircle2 size={22} color="var(--semantic-success)" style={{ flexShrink: 0 }} />
            <div>
              <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                No Significant Nutrient Deficiency Detected
              </strong>
              <p style={{ margin: '3px 0 0', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Measured soil nutrient levels satisfy the baseline requirements for {crop} at {growthStage} stage. Additional chemical top-dressing is currently not indicated.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Deficiency is detected! Map nutrient recommendation
  let nutrientName = 'Nitrogen (N)';
  let suggestedFertilizer = 'Urea / Ammonium Sulphate';
  let nutrientRole = 'Supports vegetative shoot expansion and chlorophyll development.';

  if (priorityNutrient === 'phosphorus') {
    nutrientName = 'Phosphorus (P)';
    suggestedFertilizer = 'Di-Ammonium Phosphate (DAP) or Single Super Phosphate (SSP)';
    nutrientRole = 'Stimulates root elongation, early seedling establishment, and flowering.';
  } else if (priorityNutrient === 'potassium') {
    nutrientName = 'Potassium (K)';
    suggestedFertilizer = 'Muriate of Potash (MOP) or Sulfate of Potash (SOP)';
    nutrientRole = 'Enhances drought resistance, stomatal regulation, and fruit quality.';
  }

  return (
    <div className="card" style={{ borderLeft: '4px solid var(--forest-dark)' }}>
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FlaskConical size={18} color="var(--forest-dark)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>
            NUTRIENT SUPPORT {hasActiveDisease ? '(Secondary to Disease Control)' : ''}
          </h3>
        </div>
        <StatusBadge label="DEFICIENCY DETECTED" variant="warning" icon="warning" size="sm" />
      </div>

      <div className="card-body">
        {hasActiveDisease && (
          <div style={{ padding: '12px 14px', background: 'var(--semantic-warning-bg)', border: '1px solid var(--semantic-warning-border)', borderRadius: 'var(--radius-sm)', marginBottom: '16px', fontSize: '12.5px', color: 'var(--semantic-warning-text)', lineHeight: 1.5 }}>
            <strong>Note on Advisory Sequence:</strong> Disease management must be completed before applying additional fertilizer. Nitrogen applied during severe fungal infection can exacerbate pathogen virulence.
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '16px', background: 'var(--bg-surface-soft)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Primary Deficit
            </span>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--forest-dark)', marginTop: '2px' }}>
              {nutrientName}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Deficiency Index
            </span>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {deficiency.toFixed(2)}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Target Crop Stage
            </span>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', textTransform: 'capitalize', marginTop: '2px' }}>
              {growthStage}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Suggested Input
            </span>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--forest-dark)', marginTop: '2px' }}>
              {suggestedFertilizer}
            </div>
          </div>
        </div>

        <div style={{ marginBottom: '14px' }}>
          <h4 style={{ fontSize: '13px', color: 'var(--forest-dark)', marginBottom: '4px' }}>
            Agronomic Purpose:
          </h4>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
            {nutrientRole}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '12px 14px', background: 'var(--bg-surface-soft)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', fontSize: '12.5px' }}>
          <Info size={16} color="var(--forest-dark)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong style={{ color: 'var(--text-primary)' }}>Application Rate & Dosage: </strong>
            <span style={{ color: 'var(--text-secondary)' }}>
              Exact application rate requires soil-test / local agronomist verification according to State Agricultural University (SAU) package of practices for your specific soil texture and field moisture.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
