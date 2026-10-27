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
    forecast_horizon_hours?: number;
    peak_intensity_mm_hr?: number;
    duration_hours_fraction?: number;
    risk_formula?: string;
    washoff_risk_level?: string;
    leaching_risk_level?: string;
    freshness_status?: string;
    is_cached?: boolean;
    is_estimated?: boolean;
    observation_time?: string | null;
    retrieval_time?: string | null;
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
    classifier_score?: number;
    severity?: string;
    severity_qualification?: string;
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
    benchmark_price?: number;
    observed_price?: number;
    mandi_name?: string;
    market_formula?: string;
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
  const weatherStatus = weather?.status || 'AVAILABLE';
  const weatherAvail = weather?.is_available !== false && !['UNAVAILABLE', 'TIMEOUT', 'INVALID'].includes(weatherStatus);
  let weatherStatusText = 'Low weather risk';
  let weatherBadgeVariant: BadgeVariant = 'success';
  let weatherBadgeLabel = 'SAFE';

  if (!weatherAvail) {
    if (weatherStatus === 'TIMEOUT') {
      weatherStatusText = 'Weather request timed out';
      weatherBadgeVariant = 'warning';
      weatherBadgeLabel = 'TIMEOUT';
    } else {
      weatherStatusText = 'Weather telemetry offline';
      weatherBadgeVariant = 'neutral';
      weatherBadgeLabel = 'OFFLINE';
    }
  } else if (weather?.freshness_status === 'CACHED' || weather?.is_cached) {
    weatherStatusText = 'Cached forecast observation';
    weatherBadgeVariant = 'info';
    weatherBadgeLabel = 'CACHED';
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
          style={{ fontSize: '11px', padding: '5px 10px' }}
          type="button"
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
              <span className="signal-name">Weather (Open-Meteo)</span>
              <div className="signal-status-text">{weatherStatusText}</div>
            </div>
            <p className="signal-detail">
              {weatherAvail
                ? weather?.risk_explanation || 'Precipitation safety evaluated deterministically.'
                : 'Standard protective safety margins applied.'}
            </p>
            {showTechnical && weatherAvail && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Composite Risk: <strong style={{ color: 'var(--text-primary)' }}>{Number(weather?.rainfall_risk || 0).toFixed(3)}</strong> (Horizon: {weather?.forecast_horizon_hours || 48}h)</div>
                <div>Max Precip Prob: <strong style={{ color: 'var(--text-primary)' }}>{weather?.precipitation_probability ?? 0}%</strong> · Rain: <strong style={{ color: 'var(--text-primary)' }}>{Number(weather?.rainfall_amount_mm || 0).toFixed(1)} mm</strong></div>
                {weather?.peak_intensity_mm_hr !== undefined && (
                  <div>Peak Intensity: <strong style={{ color: 'var(--text-primary)' }}>{weather.peak_intensity_mm_hr} mm/hr</strong></div>
                )}
                <div style={{ marginTop: '2px', display: 'flex', gap: '8px' }}>
                  <span>Foliar Washoff: <strong style={{ color: weather?.washoff_risk_level === 'HIGH' ? 'var(--semantic-danger-text)' : 'var(--text-primary)' }}>{weather?.washoff_risk_level || 'LOW'}</strong></span>
                  <span>·</span>
                  <span>Leaching: <strong style={{ color: weather?.leaching_risk_level === 'HIGH' ? 'var(--semantic-danger-text)' : 'var(--text-primary)' }}>{weather?.leaching_risk_level || 'LOW'}</strong></span>
                </div>
                {weather?.risk_formula && (
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '3px', background: 'var(--bg-surface)', padding: '4px 6px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                    {weather.risk_formula}
                  </div>
                )}
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
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '8px' }}>
                NPK Status: <strong style={{ color: 'var(--text-primary)' }}>{soil?.npk_available ? 'MEASURED' : 'UNMEASURED'}</strong>
                {soil?.overall_deficiency !== null && soil?.overall_deficiency !== undefined && (
                  <span> · Deficiency: <strong style={{ color: 'var(--text-primary)' }}>{Number(soil.overall_deficiency).toFixed(2)}</strong></span>
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
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '8px' }}>
                Confidence: <strong style={{ color: 'var(--text-primary)' }}>{Math.round((disease.confidence || 0) * 100)}%</strong> · Gate: <strong style={{ color: 'var(--text-primary)' }}>{disease.actionable ? 'PASSED' : 'BLOCKED'}</strong>
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
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '8px' }}>
                Score: <strong style={{ color: 'var(--text-primary)' }}>{Number(market?.market_score || 0).toFixed(2)}</strong>
                {market?.current_price ? <span> · Rate: <strong style={{ color: 'var(--text-primary)' }}>₹{market.current_price}</strong></span> : null}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
