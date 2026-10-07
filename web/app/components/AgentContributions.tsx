'use client';

import React from 'react';
import { CloudSun, Sprout, ShieldAlert, TrendingUp, Compass } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface AgentContributionsProps {
  weather?: any;
  soil?: any;
  disease?: any;
  market?: any;
  advisory?: any;
  finalRecommendation?: string;
}

export function AgentContributions({
  weather,
  soil,
  disease,
  market,
  advisory,
  finalRecommendation = '',
}: AgentContributionsProps) {
  const normRec = finalRecommendation.toLowerCase();

  // 1. Weather Agent
  const weatherAvail = weather?.is_available !== false && weather?.status !== 'UNAVAILABLE';
  const weatherRisk = Number(weather?.rainfall_risk || 0);
  const weatherImpact = normRec.includes('delay') || weatherRisk > 0.6 ? 'HIGH' : (weatherRisk > 0.3 ? 'MODERATE' : 'LOW');
  const weatherReason = weatherImpact === 'HIGH'
    ? 'Rainfall hazard is the primary constraint halting agrochemical field work.'
    : 'Meteorological telemetry confirms field operation suitability.';

  // 2. Soil Agent
  const npkAvail = Boolean(soil?.npk_available);
  const soilDefic = Number(soil?.overall_deficiency || 0);
  const soilImpact = normRec.includes('fertilizer') ? 'HIGH' : (npkAvail && soilDefic > 0.4 ? 'MODERATE' : 'LOW');
  const soilReason = soilImpact === 'HIGH'
    ? 'Significant nutrient deficiency directly influenced fertilizer replenishment advisory.'
    : (npkAvail ? 'Soil nutrients factored into routine background baseline.' : 'NPK unmeasured; prevented unsafe blind chemical dosing.');

  // 3. Disease Agent
  const hasDiseaseClass = Boolean(disease?.predicted_class && !disease.predicted_class.toLowerCase().includes('healthy'));
  const diseaseImpact = normRec.includes('disease') ? 'HIGH' : (hasDiseaseClass ? 'MODERATE' : 'LOW');
  const diseaseReason = diseaseImpact === 'HIGH'
    ? 'Active severe foliar pathogen detection takes precedence over routine field tasks.'
    : (hasDiseaseClass ? 'Identified foliar symptoms monitored for escalation.' : 'No active pathogen detected on plant tissue.');

  // 4. Market Agent
  const marketAvail = market?.is_available !== false && market?.status !== 'UNAVAILABLE';
  const marketImpact = marketAvail && market?.signal === 'sell' ? 'MODERATE' : 'LOW';
  const marketReason = marketImpact === 'MODERATE'
    ? 'Mandi market rate provides commercial context, subordinate to agronomic safety.'
    : 'Price trends noted; agronomic crop protection remains authoritative.';

  // 5. Advisory / Fertilizer Agent
  const advisoryImpact = 'HIGH';
  const advisoryReason = 'Synthesized weighted preliminary agronomic action scores across all specialist dimensions.';

  const agentCards = [
    {
      name: 'Disease Agent',
      icon: <ShieldAlert size={18} color="var(--semantic-danger)" />,
      status: disease?.status || (hasDiseaseClass ? 'DIAGNOSED' : 'STANDBY'),
      finding: hasDiseaseClass
        ? `${disease?.predicted_class?.replace(/___/g, ' ')} (${Math.round((disease?.confidence || 0) * 100)}% conf)`
        : 'No acute foliar pathogen detected',
      confidence: disease?.confidence ?? 0.0,
      impact: diseaseImpact,
      reason: diseaseReason,
    },
    {
      name: 'Weather Agent',
      icon: <CloudSun size={18} color="var(--semantic-info)" />,
      status: weatherAvail ? 'ONLINE' : 'FALLBACK',
      finding: weatherAvail
        ? `Rain risk: ${weatherRisk.toFixed(2)} (${weather?.risk_level || 'LOW'})`
        : 'Telemetry offline; neutral safety applied',
      confidence: weather?.confidence ?? 0.85,
      impact: weatherImpact,
      reason: weatherReason,
    },
    {
      name: 'Soil Agent',
      icon: <Sprout size={18} color="var(--forest-primary)" />,
      status: npkAvail ? 'MEASURED' : 'UNMEASURED',
      finding: npkAvail
        ? `Deficiency: ${soilDefic.toFixed(2)} (${soil?.priority_nutrient || 'balanced'})`
        : 'NPK unmeasured; safety rule triggered',
      confidence: soil?.confidence ?? (npkAvail ? 0.9 : 0.0),
      impact: soilImpact,
      reason: soilReason,
    },
    {
      name: 'Market Intelligence Agent',
      icon: <TrendingUp size={18} color="var(--teal-dark)" />,
      status: marketAvail ? 'ONLINE' : 'STANDBY',
      finding: marketAvail
        ? `Signal: ${(market?.signal || 'hold').toUpperCase()} (score ${Number(market?.market_score || 0).toFixed(2)})`
        : 'Mandi pricing offline; hold baseline',
      confidence: market?.confidence ?? 0.7,
      impact: marketImpact,
      reason: marketReason,
    },
    {
      name: 'Advisory Engine',
      icon: <Compass size={18} color="var(--forest-dark)" />,
      status: 'AUTHORITATIVE',
      finding: `Preliminary recommendation: ${String(advisory?.preliminary_recommendation || finalRecommendation).replace(/_/g, ' ')}`,
      confidence: advisory?.confidence ?? 0.85,
      impact: advisoryImpact,
      reason: advisoryReason,
    },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
      {agentCards.map((agent, i) => (
        <div
          key={i}
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {agent.icon}
              <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{agent.name}</strong>
            </div>
            <StatusBadge
              label={agent.status}
              variant={agent.status === 'ONLINE' || agent.status === 'MEASURED' || agent.status === 'AUTHORITATIVE' ? 'success' : 'neutral'}
              size="sm"
            />
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-primary)', background: 'var(--bg-surface-soft)', padding: '6px 10px', borderRadius: '4px' }}>
            <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', fontWeight: 600 }}>Key Finding</span>
            {agent.finding}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11.5px', marginTop: '2px' }}>
            <span>
              Decision Impact:{' '}
              <strong style={{ color: agent.impact === 'HIGH' ? 'var(--semantic-danger)' : agent.impact === 'MODERATE' ? 'var(--semantic-warning)' : 'var(--text-secondary)' }}>
                {agent.impact}
              </strong>
            </span>
            <span>
              Conf: <strong>{Math.round(agent.confidence * 100)}%</strong>
            </span>
          </div>

          <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.4, borderTop: '1px solid var(--border-subtle)', paddingTop: '6px' }}>
            {agent.reason}
          </p>
        </div>
      ))}
    </div>
  );
}
