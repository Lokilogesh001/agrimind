'use client';

import React from 'react';
import { CheckSquare, ArrowRight, Clock, Calendar, AlertTriangle } from 'lucide-react';

interface WorkflowStep {
  step: number;
  phase: string;
  title: string;
  desc: string;
  category?: string;
}

interface OperationalPlan {
  primary_action?: string;
  operational_state?: string;
  treatment_permission?: {
    status?: string;
    is_permitted?: boolean;
    action_instruction?: string;
    weather_hold?: boolean;
    rain_free_window_hours?: number;
    reassessment_trigger?: string;
    cultural_measures?: string;
  };
  workflow_steps?: WorkflowStep[];
  rain_free_window_hours?: number;
  reassessment_trigger?: string;
}

interface ActionPlanProps {
  recommendation: string;
  crop?: string;
  disease?: {
    predicted_class?: string | null;
    actionable?: boolean;
    severity?: string;
  } | null;
  soil?: {
    npk_available?: boolean;
    overall_deficiency?: number | null;
    priority_nutrient?: string;
  } | null;
  weather?: {
    risk_level?: string;
    rainfall_risk?: number;
  } | null;
  operationalPlan?: OperationalPlan | null;
}

export function ActionPlan({
  recommendation,
  crop = 'Crop',
  disease,
  soil,
  weather,
  operationalPlan,
}: ActionPlanProps) {
  // If backend provided authoritative unified operational plan, use it directly (Boil the Lake)
  if (operationalPlan?.workflow_steps && operationalPlan.workflow_steps.length >= 3) {
    const s1 = operationalPlan.workflow_steps[0];
    const s2 = operationalPlan.workflow_steps[1];
    const s3 = operationalPlan.workflow_steps[2];
    return (
      <div className="card" id="action-plan-section">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckSquare size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0 }}>WHAT SHOULD I DO?</h3>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
            Unified Coordinated Operational Plan
          </span>
        </div>

        <div className="card-body">
          <div className="action-plan-grid">
            <div className="action-step-card step-now">
              <div className="step-label">
                <Clock size={12} />
                <span>{s1.phase || 'NOW · Immediate'}</span>
              </div>
              <div className="step-title">{s1.title}</div>
              <div className="step-description">{s1.desc}</div>
            </div>

            <div className="action-step-card step-next">
              <div className="step-label">
                <ArrowRight size={12} />
                <span>{s2.phase || 'NEXT · Follow-up'}</span>
              </div>
              <div className="step-title">{s2.title}</div>
              <div className="step-description">{s2.desc}</div>
            </div>

            <div className="action-step-card step-then">
              <div className="step-label">
                <Calendar size={12} />
                <span>{s3.phase || 'THEN · Subsequent'}</span>
              </div>
              <div className="step-title">{s3.title}</div>
              <div className="step-description">{s3.desc}</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const normRec = String(recommendation || 'monitor').toLowerCase();
  const weatherRiskHigh = (weather?.risk_level || '').toUpperCase() === 'HIGH' || (weather?.rainfall_risk ?? 0) > 0.4;
  const hasDisease = Boolean(
    disease?.predicted_class &&
    !disease.predicted_class.toLowerCase().includes('healthy') &&
    disease.actionable
  );

  let nowStep = {
    title: 'Conduct Routine Field Scouting',
    desc: `Inspect your ${crop} crop for initial pest or disease symptoms and ensure uniform canopy development.`,
  };

  let nextStep = {
    title: 'Maintain Scheduled Irrigation',
    desc: 'Verify soil moisture profile at the root zone and adhere to standard water management practice.',
  };

  let thenStep = {
    title: 'Monitor Crop Stage Transition',
    desc: 'Prepare for upcoming phenological stage nutrition and record crop growth observations.',
  };

  // Safe fallback if operationalPlan not provided: enforce deterministic weather-first safety
  if (normRec.includes('delay') || weatherRiskHigh) {
    nowStep = {
      title: 'Suspend Foliar Spraying & Soil Broadcast',
      desc: 'Immediately delay all chemical sprays and fertilizer applications due to elevated rainfall risk (run-off and wash-off hazard).',
    };
    nextStep = {
      title: hasDisease ? 'Sanitize & Prune Affected Foliage (Cultural)' : 'Inspect Furrows & Farm Drainage',
      desc: hasDisease
        ? 'Safely prune blighted leaves and clear waterlogged furrows without applying chemical fungicides until rain subsides.'
        : 'Clear field drainage channels to prevent root zone water stagnation during forecast rain events.',
    };
    thenStep = {
      title: 'Reassess After 24–48h Rain-Free Window',
      desc: 'Verify that canopy is completely dry and precipitation risk < 30% before resuming any approved chemical intervention.',
    };
  } else if (normRec.includes('disease') || normRec === 'disease_management_first') {
    nowStep = {
      title: 'Sanitize Affected Plant Debris',
      desc: 'Remove severely blighted plant material and dispose outside cultivation boundaries.',
    };
    nextStep = {
      title: 'Apply CIBRC-Verified Plant Protection',
      desc: 'Apply registered formulation under clear canopy conditions with PPE.',
    };
    thenStep = {
      title: 'Evaluate Pathogen Stabilization in 3–5 Days',
      desc: 'Inspect newly emerged growth before resuming routine fertilizer nutrition.',
    };
  } else if (normRec.includes('fertilizer') || normRec.includes('apply_fertilizer')) {
    const nutrient = soil?.priority_nutrient ? soil.priority_nutrient.toUpperCase() : 'balanced nutrients';
    nowStep = {
      title: `Prepare ${nutrient} Replenishment`,
      desc: `Prepare recommended fertilizer formulation to correct verified ${nutrient} deficiency under current soil moisture.`,
    };
    nextStep = {
      title: 'Apply During Cool Field Hours',
      desc: 'Apply fertilizer in early morning or late afternoon into moist soil to minimize volatilization and root burn.',
    };
    thenStep = {
      title: 'Assess Crop Response in 14 Days',
      desc: 'Observe canopy color and new shoot vigor to confirm corrective nutrient absorption.',
    };
  } else if (!soil?.npk_available) {
    thenStep = {
      title: 'Obtain Soil Health Card Test',
      desc: 'Submit field soil samples to the nearest Krishi Vigyan Kendra (KVK) to enable precise nutrient balancing.',
    };
  }

  return (
    <div className="card" id="action-plan-section">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckSquare size={18} color="var(--forest-dark)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>WHAT SHOULD I DO?</h3>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>
          3-Step Action Workflow
        </span>
      </div>

      <div className="card-body">
        <div className="action-plan-grid">
          {/* Step 1: NOW */}
          <div className="action-step-card step-now">
            <div className="step-label">
              <Clock size={12} />
              <span>NOW · Immediate</span>
            </div>
            <div className="step-title">{nowStep.title}</div>
            <div className="step-description">{nowStep.desc}</div>
          </div>

          {/* Step 2: NEXT */}
          <div className="action-step-card step-next">
            <div className="step-label">
              <ArrowRight size={12} />
              <span>NEXT · Follow-up</span>
            </div>
            <div className="step-title">{nextStep.title}</div>
            <div className="step-description">{nextStep.desc}</div>
          </div>

          {/* Step 3: THEN */}
          <div className="action-step-card step-then">
            <div className="step-label">
              <Calendar size={12} />
              <span>THEN · Subsequent</span>
            </div>
            <div className="step-title">{thenStep.title}</div>
            <div className="step-description">{thenStep.desc}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
