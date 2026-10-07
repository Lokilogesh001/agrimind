'use client';

import React, { useState } from 'react';
import { RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

interface DecisionChangeTriggersProps {
  triggers?: string[];
  reEvaluationTrigger?: string;
  recommendation?: string;
}

export function DecisionChangeTriggers({
  triggers = [],
  reEvaluationTrigger,
  recommendation,
}: DecisionChangeTriggersProps) {
  const [expanded, setExpanded] = useState(false);

  // Fallback default triggers based on recommendation if backend list is empty
  let displayTriggers = triggers && triggers.length > 0 ? triggers : [];

  if (displayTriggers.length === 0) {
    const normRec = String(recommendation || '').toLowerCase();
    if (normRec.includes('disease')) {
      displayTriggers = [
        'Disease confidence drops below the 0.60 safety threshold on field inspection.',
        'Target plant pathogen symptoms resolve following prescribed treatment spray.',
        'Selected crop verification confirms leaf image did not match the target crop.',
      ];
    } else if (normRec.includes('delay')) {
      displayTriggers = [
        'Rainfall risk decreases below 0.30 over the next 24-hour meteorological cycle.',
        'Soil drainage status improves sufficiently to prevent agrochemical wash-off.',
        'Immediate local radar confirms no precipitation within the treatment zone.',
      ];
    } else if (normRec.includes('fertilizer')) {
      displayTriggers = [
        'New measured Soil Health Card values confirm nutrient targets have been restored.',
        'Imminent rainfall forecast increases risk of nutrient leaching, triggering a temporary delay.',
        'Crop transitions to a growth stage requiring altered N-P-K nutrient balancing.',
      ];
    } else {
      displayTriggers = [
        'Leaf imaging reveals acute pathogen symptoms with actionable confidence.',
        'Measured soil testing is submitted indicating critical macro-nutrient deficiency.',
        'Significant meteorological shifts produce heavy rainfall hazards.',
      ];
    }
  }

  return (
    <div className="card">
      <div
        className="card-header"
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <RefreshCw size={16} color="var(--forest-primary)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>WHAT WOULD CHANGE THIS DECISION?</h3>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ fontSize: '11px', padding: '3px 8px' }}
        >
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          <span>{expanded ? 'Hide Factors' : 'View Triggers'}</span>
        </button>
      </div>

      {expanded && (
        <div className="card-body">
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            AgriMind continuously evaluates field conditions. This advisory will automatically adapt if any of the following events occur:
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {displayTriggers.map((t, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '10px 12px',
                  background: 'var(--bg-surface-soft)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12.5px',
                  color: 'var(--text-primary)',
                }}
              >
                <span
                  style={{
                    color: 'var(--forest-primary)',
                    fontWeight: 700,
                    lineHeight: 1,
                    marginTop: '2px',
                  }}
                >
                  ⚡
                </span>
                <span>{t}</span>
              </div>
            ))}

            {reEvaluationTrigger && (
              <div
                style={{
                  padding: '10px 12px',
                  background: 'var(--mint-tint)',
                  border: '1px solid var(--mint-tint-border)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '12.5px',
                  color: 'var(--teal-dark)',
                  marginTop: '4px',
                }}
              >
                <strong>Scheduled Re-Evaluation:</strong> {reEvaluationTrigger}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
