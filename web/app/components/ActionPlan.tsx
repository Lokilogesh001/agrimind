'use client';

import React from 'react';
import { CheckSquare, ArrowRight, Clock, Calendar, AlertTriangle } from 'lucide-react';

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
}

export function ActionPlan({
  recommendation,
  crop = 'Crop',
  disease,
  soil,
  weather,
}: ActionPlanProps) {
  const normRec = String(recommendation || 'monitor').toLowerCase();
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

  if (normRec.includes('disease') || normRec === 'disease_management_first') {
    nowStep = {
      title: 'Prioritize Disease Containment',
      desc: 'Inspect affected foliage immediately. Remove and destroy severely infected plant debris to halt pathogen transmission.',
    };
    nextStep = {
      title: 'Apply Verified Disease Control',
      desc: 'Apply recommended plant protection treatment according to verified agricultural guidance, wearing appropriate protective equipment.',
    };
    thenStep = {
      title: 'Address Nutrients After Control',
      desc: 'Re-evaluate disease pressure in 3–5 days. Nutrient supplementation may proceed once pathogen activity is stabilized.',
    };
  } else if (normRec.includes('delay')) {
    nowStep = {
      title: 'Suspend Field Chemical Applications',
      desc: 'Immediately postpone all fertilizer broadcasting, foliar spraying, and chemical applications due to imminent precipitation.',
    };
    nextStep = {
      title: 'Inspect Farm Drainage Channels',
      desc: 'Ensure drainage furrows and field bunds are clear to avoid water stagnation around root zones during rainfall.',
    };
    thenStep = {
      title: 'Re-check Weather in 24–48 Hours',
      desc: 'Resume planned agrochemical interventions once precipitation risk clears and soil surface is trafficable.',
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
          <CheckSquare size={17} color="var(--forest-primary)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>WHAT SHOULD I DO?</h3>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600 }}>
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
