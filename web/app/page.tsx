'use client';

import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { FarmContextCard } from './components/FarmContextCard';
import { AdvisoryHero } from './components/AdvisoryHero';
import { ActionPlan } from './components/ActionPlan';
import { DecisionSignals } from './components/DecisionSignals';
import { WhyDecisionCard } from './components/WhyDecisionCard';
import { DecisionChangeTriggers } from './components/DecisionChangeTriggers';
import { DiseaseActionCard } from './components/DiseaseActionCard';
import { NutrientSupportCard } from './components/NutrientSupportCard';
import { NearbyStoresCard } from './components/NearbyStoresCard';
import { PriceCard } from './components/PriceCard';
import { DecisionPath } from './components/DecisionPath';
import { AuditPanel } from './components/AuditPanel';
import { FeedbackCard } from './components/FeedbackCard';
import { FarmInputForm } from './components/FarmInputForm';
import { OrchestrationLoader } from './components/OrchestrationLoader';
import { AgentContributions } from './components/AgentContributions';
import { EvidencePanel } from './components/EvidencePanel';
import {
  Sprout,
  ShieldCheck,
  ChevronDown,
  ArrowUp,
  SlidersHorizontal,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Home() {
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeView, setActiveView] = useState<'farmer' | 'evidence'>('farmer');

  // Preserve active field inputs for context display
  const [activeScenario, setActiveScenario] = useState<{
    locationName: string;
    lat: number | null;
    lon: number | null;
    crop: string;
    growthStage: string;
    soilMode: string;
    soilType: string;
    npk: { n: number | null; p: number | null; k: number | null };
    farmArea: string;
    irrigationMethod: string;
    sowingDate: string;
    currentPrice: string;
    hasImage: boolean;
  }>({
    locationName: 'Madurai, Tamil Nadu, India',
    lat: 9.9252,
    lon: 78.1198,
    crop: 'Tomato',
    growthStage: 'flowering',
    soilMode: 'measured',
    soilType: 'Red Soil',
    npk: { n: 180, p: 24, k: 190 },
    farmArea: '2.5',
    irrigationMethod: 'Drip',
    sowingDate: '',
    currentPrice: '2000',
    hasImage: false,
  });

  // Execute advisory run
  const handleRunAdvisory = async (payload: {
    crop: string;
    growthStage: string;
    locationName: string;
    lat: number | null;
    lon: number | null;
    soilMode: 'automatic' | 'manual' | 'measured' | 'report';
    soilType: string;
    n: string;
    p: string;
    k: string;
    farmArea: string;
    irrigationMethod: string;
    sowingDate: string;
    currentPrice: string;
    priceHistory: string;
    image: File | null;
    diseaseModel?: string;
    leafCropSelection?: string;
  }) => {
    setLoading(true);
    setError('');
    setResult(null);

    // Save field scenario snapshot
    setActiveScenario({
      locationName: payload.locationName,
      lat: payload.lat,
      lon: payload.lon,
      crop: payload.crop,
      growthStage: payload.growthStage,
      soilMode: payload.soilMode,
      soilType: payload.soilType,
      npk: {
        n: payload.n ? Number(payload.n) : null,
        p: payload.p ? Number(payload.p) : null,
        k: payload.k ? Number(payload.k) : null,
      },
      farmArea: payload.farmArea,
      irrigationMethod: payload.irrigationMethod,
      sowingDate: payload.sowingDate,
      currentPrice: payload.currentPrice,
      hasImage: Boolean(payload.image),
    });

    try {
      let data: any;

      let effectiveSoilType = '';
      let effectiveSoilMode = '';
      let nVal: number | null = null;
      let pVal: number | null = null;
      let kVal: number | null = null;

      if (payload.soilMode === 'automatic') {
        effectiveSoilMode = 'LOCATION_ESTIMATED';
      } else if (payload.soilMode === 'manual') {
        effectiveSoilType = payload.soilType.toLowerCase().replace(' ', '_');
        effectiveSoilMode = 'USER_SELECTED';
      } else if (payload.soilMode === 'measured') {
        effectiveSoilType = payload.soilType.toLowerCase().replace(' ', '_');
        effectiveSoilMode = 'MEASURED';
        nVal = payload.n ? Number(payload.n) : null;
        pVal = payload.p ? Number(payload.p) : null;
        kVal = payload.k ? Number(payload.k) : null;
      } else if (payload.soilMode === 'report') {
        effectiveSoilMode = 'USER_SELECTED';
        effectiveSoilType = payload.soilType.toLowerCase().replace(' ', '_');
      }

      if (payload.image) {
        const body = new FormData();
        body.append('crop', payload.crop);
        body.append('growth_stage', payload.growthStage);
        body.append('location_name', payload.locationName);
        if (payload.lat !== null) body.append('lat', String(payload.lat));
        if (payload.lon !== null) body.append('lon', String(payload.lon));
        if (nVal !== null) body.append('n', String(nVal));
        if (pVal !== null) body.append('p', String(pVal));
        if (kVal !== null) body.append('k', String(kVal));
        if (effectiveSoilType) body.append('soil_type', effectiveSoilType);
        if (effectiveSoilMode) body.append('soil_mode', effectiveSoilMode);
        if (payload.currentPrice) body.append('current_price', payload.currentPrice);
        if (payload.priceHistory) body.append('price_history', payload.priceHistory);
        if (payload.farmArea) body.append('farm_area', payload.farmArea);
        if (payload.irrigationMethod) body.append('irrigation_method', payload.irrigationMethod);
        if (payload.diseaseModel) body.append('disease_model', payload.diseaseModel);
        if (payload.leafCropSelection) body.set('crop', payload.leafCropSelection);
        body.append('image', payload.image);

        const res = await fetch(`${API}/api/advisory/upload`, {
          method: 'POST',
          body,
        });
        if (!res.ok) throw new Error(await res.text());
        data = await res.json();
      } else {
        const reqPayload: any = {
          crop: payload.crop,
          growth_stage: payload.growthStage,
          location_name: payload.locationName,
          lat: payload.lat,
          lon: payload.lon,
          soil_type: effectiveSoilType,
          soil_mode: effectiveSoilMode,
          current_price: payload.currentPrice ? Number(payload.currentPrice) : 0,
          price_history: payload.priceHistory ? payload.priceHistory.split(',').filter(Boolean).map(Number) : [],
          disease_model: payload.diseaseModel || undefined,
        };
        if (nVal !== null) reqPayload.n = nVal;
        if (pVal !== null) reqPayload.p = pVal;
        if (kVal !== null) reqPayload.k = kVal;
        if (payload.farmArea) reqPayload.farm_area = Number(payload.farmArea);
        if (payload.irrigationMethod) reqPayload.irrigation_method = payload.irrigationMethod;
        if (payload.sowingDate) reqPayload.sowing_date = payload.sowingDate;

        const res = await fetch(`${API}/api/advisory`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(reqPayload),
        });
        if (!res.ok) throw new Error(await res.text());
        data = await res.json();
      }

      setResult(data);
      setActiveView('farmer');
    } catch (e: any) {
      setError(e.message || 'Unable to communicate with AgriMind backend.');
    } finally {
      setLoading(false);
    }
  };

  // Automatically scroll to results on generation
  useEffect(() => {
    if (result && !loading) {
      const el = document.getElementById('advisory-results-section');
      if (el) {
        setTimeout(() => {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
      }
    }
  }, [result, loading]);

  // Submit field feedback
  const handleFeedbackSubmit = async (feedbackData: {
    run_id: string;
    farmer_action_taken: string;
    outcome_reported: string;
    comment: string;
  }) => {
    const res = await fetch(`${API}/api/feedback`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(feedbackData),
    });
    if (!res.ok) throw new Error(await res.text());
    return true;
  };

  const scrollToActions = () => {
    const el = document.getElementById('action-plan-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const scrollToForm = () => {
    const el = document.getElementById('farm-configuration-workspace');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="app-container">
      {/* 1. Header with Brand Identity, Online Status, and View Switcher */}
      <Header
        activeView={activeView}
        onViewChange={setActiveView}
        apiConnected={!error}
      />

      {/* Main Full-Width Workspace Flow */}
      <main className="workspace-page">
        {/* 2. Page Title & Context Description */}
        <div className="page-intro-banner">
          <div className="eyebrow">
            <ShieldCheck size={13} />
            <span>Autonomous Agricultural Decision Support Cluster</span>
          </div>
          <h1 className="page-intro-title">
            Farm Crop Advisory & Field Parameter Workspace
          </h1>
          <p className="page-intro-desc">
            Configure your farm location, soil fertility, and optional leaf disease imagery across the workspace below. AgriMind coordinates specialist meteorology, soil chemistry, pathology, and market intelligence agents to generate an authoritative, safety-guarded field action plan.
          </p>
        </div>

        {/* 3. Full-Width Horizontal Farm Configuration Form */}
        <section id="farm-configuration-workspace" className="form-workspace-section">
          <FarmInputForm
            apiBase={API}
            onRunAdvisory={handleRunAdvisory}
            loading={loading}
            error={error}
          />
        </section>

        {/* 4. Compact Orchestration Loader (Visible only during processing) */}
        {loading && (
          <section className="orchestration-section" style={{ marginTop: '12px' }}>
            <OrchestrationLoader hasImage={activeScenario.hasImage} />
          </section>
        )}

        {/* 5. Full-Width Advisory Results Section (Appears below the form) */}
        {result && !loading && (
          <section id="advisory-results-section" className="results-workspace-section">
            {/* Results Section Anchor Bar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', padding: '0 4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="eyebrow">GENERATED ADVISORY OUTPUT</span>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  · Run ID: {result.run_id?.substring(0, 8)}…
                </span>
              </div>
              <button
                type="button"
                onClick={scrollToForm}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                <ArrowUp size={12} />
                <span>Modify Parameters</span>
              </button>
            </div>

            {/* Farm Context Summary Chips Card */}
            <FarmContextCard
              locationName={result.location?.location_name || activeScenario.locationName}
              crop={result.advisory?.crop?.crop || activeScenario.crop}
              growthStage={result.advisory?.crop?.growth_stage || activeScenario.growthStage}
              soilMode={activeScenario.soilMode}
              soilType={activeScenario.soilType}
              farmArea={activeScenario.farmArea}
              irrigationMethod={activeScenario.irrigationMethod}
              sowingDate={activeScenario.sowingDate}
              npk={activeScenario.npk}
            />

            {/* VIEW 1: FARMER-FACING ADVISORY (Default) */}
            {activeView === 'farmer' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginTop: '20px' }}>
                {/* 1. HERO: TODAY'S ADVISORY */}
                <AdvisoryHero
                  recommendation={result.recommendation}
                  explanation={result.explanation}
                  confidence={result.confidence}
                  disease={result.disease}
                  weatherRisk={result.weather_risk}
                  soilStatus={result.soil_nutrient_status}
                  onScrollToAction={scrollToActions}
                />

                {/* 2. ACTION PLAN: WHAT SHOULD I DO? (NOW, NEXT, THEN) */}
                <ActionPlan
                  recommendation={result.recommendation}
                  crop={activeScenario.crop}
                  disease={result.disease}
                  soil={result.soil}
                  weather={result.weather}
                  operationalPlan={result.operational_plan}
                />

                {/* 3. DECISION SIGNALS (4-Card Telemetry Grid) */}
                <DecisionSignals
                  weather={result.weather}
                  soil={result.soil}
                  disease={result.disease}
                  market={result.market}
                />

                {/* 4. WHY THIS DECISION? (Agronomic Rationale) */}
                <WhyDecisionCard
                  recommendation={result.recommendation}
                  conflicts={result.conflicts}
                  safetyConstraints={result.safety_constraints}
                  reEvaluationTrigger={result.re_evaluation_trigger}
                  weather={result.weather}
                  soil={result.soil}
                  disease={result.disease}
                  llmExplanation={result.llm_explanation}
                  evidence={result.evidence}
                />

                {/* 5. DECISION CHANGE TRIGGERS (Invalidation thresholds) */}
                <DecisionChangeTriggers
                  triggers={result.decision_change_triggers}
                  reEvaluationTrigger={result.re_evaluation_trigger}
                  recommendation={result.recommendation}
                />

                {/* 6. SPECIALIST MODULES (Disease Management & Soil Nutrition in 2-column grid) */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '24px' }}>
                  {result.disease && (
                    <DiseaseActionCard
                      disease={result.disease}
                      crop={activeScenario.crop}
                      treatmentPermission={result.treatment_permission || result.operational_plan?.treatment_permission}
                      recommendation={result.recommendation}
                    />
                  )}

                  <NutrientSupportCard
                    soil={result.soil}
                    crop={activeScenario.crop}
                    growthStage={activeScenario.growthStage}
                    hasActiveDisease={Boolean(
                      result.disease?.predicted_class &&
                      !result.disease.predicted_class.toLowerCase().includes('healthy') &&
                      result.disease.actionable
                    )}
                  />
                </div>

                {/* 7. LOCAL COMMERCE & PRICE TRANSPARENCY (2-column grid) */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '24px' }}>
                  <NearbyStoresCard
                    locationName={result.location?.location_name || activeScenario.locationName}
                    coordinates={{
                      lat: result.location?.latitude ?? activeScenario.lat,
                      lon: result.location?.longitude ?? activeScenario.lon,
                    }}
                    stores={result.nearby_stores || []}
                  />

                  <PriceCard
                    crop={activeScenario.crop}
                    benchmarkPrice={result.market?.benchmark_price ?? (activeScenario.currentPrice ? Number(activeScenario.currentPrice) : null)}
                    observedPrice={result.market?.observed_price ?? null}
                    mandiName={result.market?.mandi_name}
                    commodityGrade={result.market?.commodity_grade}
                    retrievalTimestamp={result.market?.retrieval_timestamp}
                    marketScore={result.market?.market_score}
                    marketSignal={result.market?.signal}
                    marketFormula={result.market?.market_formula}
                    phenologyNote={result.market?.phenology_note}
                  />
                </div>

                {/* 8. HOW AGRIMIND REACHED THIS DECISION (Execution Path) */}
                <DecisionPath
                  crop={activeScenario.crop}
                  location={result.location?.location_name || activeScenario.locationName}
                  recommendation={result.recommendation}
                  weather={result.weather}
                  soil={result.soil}
                  disease={result.disease}
                  market={result.market}
                  conflicts={result.conflicts}
                  safetyConstraints={result.safety_constraints}
                />

                {/* 9. AGENT CONTRIBUTIONS */}
                <AgentContributions
                  weather={result.weather}
                  soil={result.soil}
                  disease={result.disease}
                  market={result.market}
                  advisory={result.advisory}
                  finalRecommendation={result.recommendation}
                />

                {/* 10. ICAR SUPPORTING EVIDENCE */}
                {result.evidence && result.evidence.length > 0 && (
                  <EvidencePanel evidenceList={result.evidence} />
                )}

                {/* 11. FIELD FEEDBACK LOOP */}
                <FeedbackCard
                  runId={result.run_id}
                  onFeedbackSubmit={handleFeedbackSubmit}
                />
              </div>
            )}

            {/* VIEW 2: EVIDENCE & AUDIT (Deep Observability) */}
            {activeView === 'evidence' && (
              <div style={{ marginTop: '20px' }}>
                <AuditPanel result={result} />
              </div>
            )}
          </section>
        )}
      </main>

      {/* Modern Accessible Footer */}
      <footer>
        <p>
          AgriMind Decision Support · Multi-Agent Orchestration with Deterministic Agronomic Safety Guard · LLMs serve an explanation role only · Field agronomy judgment must validate all physical chemical applications.
        </p>
      </footer>
    </div>
  );
}
