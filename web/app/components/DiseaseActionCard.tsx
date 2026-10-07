'use client';

import React from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  FileCheck,
  CheckCircle2,
  HelpCircle,
} from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface DiseaseActionCardProps {
  disease?: {
    predicted_class?: string | null;
    confidence?: number;
    severity?: string;
    actionable?: boolean;
    crop_mismatch?: boolean;
    crop_detected?: string;
    normalized_disease?: string;
    block_reason?: string;
    status?: string;
  } | null;
  crop?: string;
  evidenceText?: string;
}

export function DiseaseActionCard({
  disease,
  crop = 'Crop',
  evidenceText,
}: DiseaseActionCardProps) {
  if (!disease || !disease.predicted_class) {
    return (
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={17} color="var(--forest-primary)" />
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
            <ShieldCheck size={17} color="var(--semantic-success)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>DISEASE MANAGEMENT</h3>
          </div>
          <StatusBadge label="HEALTHY CROP" variant="success" icon="shield-check" size="sm" />
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle2 size={20} color="var(--semantic-success)" />
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

  const confidence = disease.confidence ?? 0;
  const confPercent = Math.round(confidence * 100);
  const isLowConfidence = confidence < 0.60;
  const isMismatch = Boolean(disease.crop_mismatch);
  const isActionable = Boolean(disease.actionable);

  const cleanName = disease.predicted_class
    .replace(/___/g, ' ')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());

  // Determine Verified Recommended Action from agronomy guidance
  let treatmentAction = 'Consult local agricultural extension or Krishi Vigyan Kendra (KVK) for certified treatment.';
  let culturalPractice = 'Remove and isolate infected foliage. Avoid overhead sprinkler irrigation to minimize spore dispersal.';

  const lowerClass = disease.predicted_class.toLowerCase();
  if (lowerClass.includes('late_blight') || lowerClass.includes('late blight')) {
    treatmentAction = 'Apply verified contact/systemic fungicide (e.g. Mancozeb 75 WP @ 2.0–2.5 g/L or Cymoxanil + Mancozeb @ 2 g/L) strictly following product label and local ICAR advisories.';
    culturalPractice = 'Ensure proper field drainage, destroy severely infected plant debris, and avoid working in wet canopies to stop zoospore spread.';
  } else if (lowerClass.includes('early_blight') || lowerClass.includes('early blight')) {
    treatmentAction = 'Foliar spray of Chlorothalonil 75 WP (2 g/L) or Mancozeb (2 g/L) at first symptom appearance.';
    culturalPractice = 'Maintain plant spacing for aeration, remove lower senescent leaves, and practice crop rotation with non-solanaceous crops.';
  } else if (lowerClass.includes('blast')) {
    treatmentAction = 'Apply Tricyclazole 75 WP @ 0.6 g/L or Isoprothiolane 40 EC @ 1.5 ml/L of water.';
    culturalPractice = 'Avoid excessive nitrogen application which predisposes foliage to blast susceptibility.';
  } else if (lowerClass.includes('bacterial')) {
    treatmentAction = 'Spray Copper Oxychloride 50 WP (2.5 g/L) + Streptocycline (0.1 g/L) upon initial detection.';
    culturalPractice = 'Sanitize cutting tools between plants; avoid field operations when leaves are damp with dew or rain.';
  }

  return (
    <div className="card" style={{ borderLeft: '4px solid var(--semantic-danger)' }}>
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert size={18} color="var(--semantic-danger)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>DISEASE MANAGEMENT</h3>
        </div>
        <StatusBadge
          label={isActionable ? 'ACTION ALLOWED' : 'ACTION BLOCKED'}
          variant={isActionable ? 'danger' : 'warning'}
          icon={isActionable ? 'danger' : 'warning'}
          size="sm"
        />
      </div>

      <div className="card-body">
        {/* Low Confidence Warning Banner */}
        {isLowConfidence && !isMismatch && (
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--semantic-warning-bg)',
              border: '1px solid var(--semantic-warning-border)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
            }}
          >
            <AlertTriangle size={18} color="var(--semantic-warning-text)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ fontSize: '13px', color: 'var(--semantic-warning-text)' }}>
                LOW CONFIDENCE DIAGNOSIS ({confPercent}%)
              </strong>
              <p style={{ margin: '2px 0 0', fontSize: '12.5px', color: 'var(--semantic-warning-text)' }}>
                Image-based diagnosis is uncertain (below 60% safety threshold). Field verification by a local agronomist or KVK is strongly recommended before applying any chemical pesticides.
              </p>
            </div>
          </div>
        )}

        {/* Crop Mismatch Banner */}
        {isMismatch && (
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--semantic-danger-bg)',
              border: '1px solid var(--semantic-danger-border)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
            }}
          >
            <AlertTriangle size={18} color="var(--semantic-danger-text)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ fontSize: '13px', color: 'var(--semantic-danger-text)' }}>
                CROP MISMATCH GUARD ACTIVATED
              </strong>
              <p style={{ margin: '2px 0 0', fontSize: '12.5px', color: 'var(--semantic-danger-text)' }}>
                Selected crop is <strong>{crop}</strong>, but leaf model detected characteristics of <strong>{disease.crop_detected || 'another crop'}</strong>. Disease-specific chemical action is strictly prohibited to prevent misapplication.
              </p>
            </div>
          </div>
        )}

        {/* Diagnosis Header Details */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '16px', background: 'var(--bg-surface-soft)', padding: '12px 14px', borderRadius: 'var(--radius-sm)' }}>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Detected Pathogen
            </span>
            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {cleanName}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Model Confidence
            </span>
            <div style={{ fontSize: '14px', fontWeight: 700, color: isLowConfidence ? 'var(--semantic-warning)' : 'var(--text-primary)' }}>
              {confPercent}%
            </div>
          </div>

          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Severity Level
            </span>
            <div style={{ fontSize: '14px', fontWeight: 700, textTransform: 'capitalize', color: disease.severity === 'high' ? 'var(--semantic-danger)' : 'var(--text-primary)' }}>
              {disease.severity || 'Moderate'}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Safety Gate
            </span>
            <div style={{ fontSize: '14px', fontWeight: 700, color: isActionable ? 'var(--semantic-success)' : 'var(--semantic-danger)' }}>
              {isActionable ? 'PASSED (≥60%)' : 'RESTRICTED'}
            </div>
          </div>
        </div>

        {/* Recommended Disease-Control Action */}
        <div style={{ marginBottom: '14px' }}>
          <h4 style={{ fontSize: '13px', color: 'var(--forest-dark)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={15} color="var(--forest-primary)" />
            Recommended Disease-Control Treatment:
          </h4>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.5, background: 'var(--bg-surface)', padding: '10px 12px', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
            {isActionable
              ? treatmentAction
              : 'Hold chemical treatment pending in-person verification. Implement cultural field sanitation measures.'}
          </p>
        </div>

        {/* Cultural & Field Sanitation */}
        <div style={{ marginBottom: '14px' }}>
          <h4 style={{ fontSize: '13px', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Cultural Management & Phytosanitary Measures:
          </h4>
          <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {culturalPractice}
          </p>
        </div>

        {/* Safety Disclaimer */}
        <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', background: 'var(--bg-surface-soft)', padding: '8px 12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
          <strong>Safety & Compliance:</strong> Always follow statutory pesticide label instructions, safety intervals (PHI), and use approved Personal Protective Equipment (PPE). Never apply agrochemicals without verifying local agricultural department registration.
        </div>
      </div>
    </div>
  );
}
