'use client';

import React, { useState } from 'react';
import {
  CloudSun,
  Sprout,
  ShieldAlert,
  TrendingUp,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { StatusBadge, BadgeVariant } from './StatusBadge';

interface DecisionSignalsProps {
  weather?: {
    is_available?: boolean;
    status?: string;
    rainfall_risk?: number;
    risk_level?: string;
    risk_explanation?: string;
    precipitation_probability?: number | null;
    rainfall_amount_mm?: number | null;
  } | null;
  soil?: {
    status?: string;
    npk_available?: boolean;
    overall_deficiency?: number | null;
    priority_nutrient?: string;
    nutrient_status?: string;
  } | null;
  disease?: {
    status?: string;
    predicted_class?: string | null;
    confidence?: number;
    severity?: string;
    actionable?: boolean;
    crop_mismatch?: boolean;
    crop_detected?: string;
  } | null;
  market?: {
    is_available?: boolean;
    status?: string;
    signal?: string;
    market_score?: number;
    current_price?: number;
  } | null;
}

export function DecisionSignals({
  weather,
  soil,
  disease,
  market,
}: DecisionSignalsProps) {
  const [showTechnical, setShowTechnical] = useState(false);

  // 1. WEATHER SIGNAL
  const weatherAvail = weather?.is_available !== false && weather?.status !== 'UNAVAILABLE';
  let weatherStatusText = 'Low weather risk';
  let weatherBadgeVariant: BadgeVariant = 'success';
  let weatherBadgeLabel = 'SAFE';

  if (!weatherAvail) {
    weatherStatusText = 'Weather telemetry offline';
    weatherBadgeVariant = 'neutral';
    weatherBadgeLabel = 'OFFLINE';
  } else {
    const riskLvl = (weather?.risk_level || 'LOW').toUpperCase();
    if (riskLvl === 'SEVERE' || riskLvl === 'HIGH') {
      weatherStatusText = 'High rainfall risk';
      weatherBadgeVariant = 'danger';
      weatherBadgeLabel = 'HIGH RISK';
    } else if (riskLvl === 'MODERATE') {
      weatherStatusText = 'Moderate rain risk';
      weatherBadgeVariant = 'warning';
      weatherBadgeLabel = 'CAUTION';
    } else {
      weatherStatusText = 'Favorable weather conditions';
      weatherBadgeVariant = 'success';
      weatherBadgeLabel = 'FAVORABLE';
    }
  }

  // 2. SOIL SIGNAL
  let soilStatusText = 'Soil profile balanced';
  let soilBadgeVariant: BadgeVariant = 'success';
  let soilBadgeLabel = 'BALANCED';

  if (!soil?.npk_available) {
    soilStatusText = 'NPK measurements unrecorded';
    soilBadgeVariant = 'info';
    soilBadgeLabel = 'UNMEASURED';
  } else if ((soil?.overall_deficiency ?? 0) > 0.6) {
    soilStatusText = `${(soil?.priority_nutrient || 'Nutrient').toUpperCase()} deficiency detected`;
    soilBadgeVariant = 'warning';
    soilBadgeLabel = 'DEFICIENT';
  } else if ((soil?.overall_deficiency ?? 0) > 0.3) {
    soilStatusText = `Mild ${soil?.priority_nutrient || 'nutrient'} variation`;
    soilBadgeVariant = 'info';
    soilBadgeLabel = 'MODERATE';
  }

  // 3. DISEASE SIGNAL
  let diseaseStatusText = 'No disease detected';
  let diseaseBadgeVariant: BadgeVariant = 'success';
  let diseaseBadgeLabel = 'CLEAR';

  const hasDiseaseClass = Boolean(
    disease?.predicted_class &&
    !disease.predicted_class.toLowerCase().includes('healthy')
  );

  if (disease?.crop_mismatch) {
    diseaseStatusText = 'Crop mismatch detected';
    diseaseBadgeVariant = 'warning';
    diseaseBadgeLabel = 'MISMATCH';
  } else if (hasDiseaseClass) {
    if (disease?.actionable) {
      diseaseStatusText = 'Active disease pressure';
      diseaseBadgeVariant = 'danger';
      diseaseBadgeLabel = 'ACTIVE';
    } else {
      diseaseStatusText = 'Uncertain disease signal';
      diseaseBadgeVariant = 'warning';
      diseaseBadgeLabel = 'UNCERTAIN';
    }
  } else if (!disease?.predicted_class) {
    diseaseStatusText = 'No leaf photo submitted';
    diseaseBadgeVariant = 'neutral';
    diseaseBadgeLabel = 'NO IMAGE';
  }

  // 4. MARKET SIGNAL
  const marketAvail = market?.is_available !== false && market?.status !== 'UNAVAILABLE';
  let marketStatusText = 'Market conditions stable';
  let marketBadgeVariant: BadgeVariant = 'mint';
  let marketBadgeLabel = 'STABLE';

  if (!marketAvail) {
    marketStatusText = 'Market telemetry offline';
    marketBadgeVariant = 'neutral';
    marketBadgeLabel = 'OFFLINE';
  } else {
    const sig = (market?.signal || 'hold').toLowerCase();
    if (sig === 'sell') {
      marketStatusText = 'Favorable price signal';
      marketBadgeVariant = 'success';
      marketBadgeLabel = 'FAVORABLE';
    } else if (sig === 'delay_sale') {
      marketStatusText = 'Hold for price appreciation';
      marketBadgeVariant = 'warning';
      marketBadgeLabel = 'HOLD';
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <span className="eyebrow">ENVIRONMENT & FIELD SIGNALS</span>
          <h3 style={{ fontSize: '15px', margin: '2px 0 0' }}>DECISION SIGNALS</h3>
        </div>

        <button
          onClick={() => setShowTechnical(!showTechnical)}
          className="btn btn-secondary btn-sm"
          style={{ fontSize: '11px', padding: '4px 8px' }}
        >
          {showTechnical ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          <span>{showTechnical ? 'Hide Telemetry' : 'Show Telemetry'}</span>
        </button>
      </div>

      <div className="card-body">
        <div className="signals-grid">
          {/* Weather Signal Card */}
          <div className="signal-card">
            <div className="signal-card-top">
              <div className="signal-icon-box signal-icon-weather">
                <CloudSun size={18} />
              </div>
              <StatusBadge label={weatherBadgeLabel} variant={weatherBadgeVariant} size="sm" />
            </div>
            <div>
              <span className="signal-name">Weather</span>
              <div className="signal-status-text">{weatherStatusText}</div>
            </div>
            <p className="signal-detail">
              {weatherAvail
                ? weather?.risk_explanation || 'Precipitation safety evaluated deterministically.'
                : 'Standard protective safety margins applied.'}
            </p>
            {showTechnical && weatherAvail && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px' }}>
                Rain risk: <strong>{Number(weather?.rainfall_risk || 0).toFixed(2)}</strong> · Rain: <strong>{Number(weather?.rainfall_amount_mm || 0).toFixed(1)} mm</strong>
              </div>
            )}
          </div>

          {/* Soil Signal Card */}
          <div className="signal-card">
            <div className="signal-card-top">
              <div className="signal-icon-box signal-icon-soil">
                <Sprout size={18} />
              </div>
              <StatusBadge label={soilBadgeLabel} variant={soilBadgeVariant} size="sm" />
            </div>
            <div>
              <span className="signal-name">Soil Health</span>
              <div className="signal-status-text">{soilStatusText}</div>
            </div>
            <p className="signal-detail">
              {soil?.npk_available
                ? `Priority nutrient: ${soil.priority_nutrient || 'Balanced'}`
                : 'Measured soil health card recommended.'}
            </p>
            {showTechnical && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px' }}>
                NPK Status: <strong>{soil?.npk_available ? 'MEASURED' : 'UNMEASURED'}</strong>
                {soil?.overall_deficiency !== null && soil?.overall_deficiency !== undefined && (
                  <span> · Deficiency: <strong>{Number(soil.overall_deficiency).toFixed(2)}</strong></span>
                )}
              </div>
            )}
          </div>

          {/* Disease Signal Card */}
          <div className="signal-card">
            <div className="signal-card-top">
              <div className="signal-icon-box signal-icon-disease">
                <ShieldAlert size={18} />
              </div>
              <StatusBadge label={diseaseBadgeLabel} variant={diseaseBadgeVariant} size="sm" />
            </div>
            <div>
              <span className="signal-name">Crop Health</span>
              <div className="signal-status-text">{diseaseStatusText}</div>
            </div>
            <p className="signal-detail">
              {hasDiseaseClass
                ? `${disease?.predicted_class?.replace(/___/g, ' ') || 'Pathogen identified'}`
                : 'No acute foliar pathogens observed.'}
            </p>
            {showTechnical && disease?.predicted_class && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px' }}>
                Confidence: <strong>{Math.round((disease.confidence || 0) * 100)}%</strong> · Gate: <strong>{disease.actionable ? 'PASSED' : 'BLOCKED'}</strong>
              </div>
            )}
          </div>

          {/* Market Signal Card */}
          <div className="signal-card">
            <div className="signal-card-top">
              <div className="signal-icon-box signal-icon-market">
                <TrendingUp size={18} />
              </div>
              <StatusBadge label={marketBadgeLabel} variant={marketBadgeVariant} size="sm" />
            </div>
            <div>
              <span className="signal-name">Market Trend</span>
              <div className="signal-status-text">{marketStatusText}</div>
            </div>
            <p className="signal-detail">
              {marketAvail
                ? `Mandi signal: ${(market?.signal || 'hold').toUpperCase()}`
                : 'Agricultural pricing telemetry offline.'}
            </p>
            {showTechnical && marketAvail && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px' }}>
                Score: <strong>{Number(market?.market_score || 0).toFixed(2)}</strong>
                {market?.current_price ? <span> · Rate: <strong>₹{market.current_price}</strong></span> : null}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
