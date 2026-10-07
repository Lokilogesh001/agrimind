'use client';

import React from 'react';
import {
  MapPin,
  Sprout,
  Calendar,
  Layers,
  Droplets,
  Ruler,
  FlaskConical,
} from 'lucide-react';

interface FarmContextProps {
  locationName: string;
  crop: string;
  growthStage: string;
  soilMode: string;
  soilType?: string;
  farmArea?: string | number | null;
  irrigationMethod?: string | null;
  sowingDate?: string | null;
  npk?: { n: number | null; p: number | null; k: number | null } | null;
  compact?: boolean;
}

export function FarmContextCard({
  locationName,
  crop,
  growthStage,
  soilMode,
  soilType,
  farmArea,
  irrigationMethod,
  sowingDate,
  npk,
  compact = false,
}: FarmContextProps) {
  const formatStage = (stage: string) => {
    return stage
      .replace(/_/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  const getSoilModeLabel = () => {
    if (soilMode === 'measured' || soilMode === 'MEASURED') return 'Soil Health Card (Measured)';
    if (soilMode === 'automatic' || soilMode === 'LOCATION_ESTIMATED') return 'Location-Estimated';
    if (soilMode === 'manual' || soilMode === 'USER_SELECTED') return `Manual (${soilType || 'Specified'})`;
    if (soilMode === 'report') return 'Soil Lab Report';
    return soilType || 'Regional Profile';
  };

  return (
    <div className="card" style={{ marginBottom: compact ? 0 : '18px' }}>
      <div className="card-header" style={{ padding: '12px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="eyebrow">
            <Sprout size={13} />
            Farm Context
          </span>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Active Field Scenario
        </span>
      </div>

      <div className="card-body" style={{ padding: '14px 18px' }}>
        <div className="context-chips-grid">
          <div className="context-chip">
            <span className="context-chip-label">
              <MapPin size={11} />
              Location
            </span>
            <span className="context-chip-value" title={locationName}>
              {locationName || 'Unspecified'}
            </span>
          </div>

          <div className="context-chip">
            <span className="context-chip-label">
              <Sprout size={11} />
              Crop
            </span>
            <span className="context-chip-value">
              {crop || 'Tomato'}
            </span>
          </div>

          <div className="context-chip">
            <span className="context-chip-label">
              <Calendar size={11} />
              Growth Stage
            </span>
            <span className="context-chip-value">
              {formatStage(growthStage || 'Vegetative')}
            </span>
          </div>

          <div className="context-chip">
            <span className="context-chip-label">
              <FlaskConical size={11} />
              Soil Method
            </span>
            <span className="context-chip-value" title={getSoilModeLabel()}>
              {getSoilModeLabel()}
            </span>
          </div>

          {farmArea && (
            <div className="context-chip">
              <span className="context-chip-label">
                <Ruler size={11} />
                Farm Area
              </span>
              <span className="context-chip-value">
                {farmArea} {Number(farmArea) === 1 ? 'acre' : 'acres'}
              </span>
            </div>
          )}

          {irrigationMethod && (
            <div className="context-chip">
              <span className="context-chip-label">
                <Droplets size={11} />
                Irrigation
              </span>
              <span className="context-chip-value">
                {irrigationMethod}
              </span>
            </div>
          )}

          {sowingDate && (
            <div className="context-chip">
              <span className="context-chip-label">
                <Calendar size={11} />
                Sown Date
              </span>
              <span className="context-chip-value">
                {sowingDate}
              </span>
            </div>
          )}

          {npk && (npk.n !== null || npk.p !== null || npk.k !== null) && (
            <div className="context-chip" style={{ gridColumn: 'span 2' }}>
              <span className="context-chip-label">
                <Layers size={11} />
                Measured N-P-K (kg/ha)
              </span>
              <span className="context-chip-value" style={{ color: 'var(--forest-dark)' }}>
                N: {npk.n ?? '—'} · P: {npk.p ?? '—'} · K: {npk.k ?? '—'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
