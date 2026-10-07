'use client';

import React, { useState } from 'react';
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
import {
  Sprout,
  Sparkles,
  HelpCircle,
  FileCheck,
  ChevronRight,
  RotateCcw,
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
    hasImage: false,
  });

  const [showInputDrawer, setShowInputDrawer] = useState(true);

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
      // Auto-switch to Advisory view on successful result
      setActiveView('farmer');
    } catch (e: any) {
      setError(e.message || 'Unable to communicate with AgriMind backend.');
    } finally {
      setLoading(false);
    }
  };

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

  return (
    <div className="app-container">
      {/* 1. Header with Forest Brand Identity & View Switcher */}
      <Header
        activeView={activeView}
        onViewChange={setActiveView}
        apiConnected={!error}
      />

      {/* Main Two-Column Layout */}
      <main className="dashboard-grid">
        {/* Left Column: Farm Context Inputs */}
        <aside className="sidebar-panel">
          <FarmInputForm
            apiBase={API}
            onRunAdvisory={handleRunAdvisory}
            loading={loading}
            error={error}
          />
        </aside>

        {/* Right Column: Advisory / Evidence Results */}
        <section className="main-advisory-content">
          {/* Loading State: Multi-Agent Orchestration Visualizer */}
          {loading && (
            <OrchestrationLoader hasImage={activeScenario.hasImage} />
          )}

          {/* Empty State before running advisory */}
          {!result && !loading && (
            <div className="empty-state">
              <div className="empty-state-icon">
                <Sprout size={28} />
              </div>
              <h3 className="empty-state-title">
                Ready for Farm Crop Advisory
              </h3>
              <p className="empty-state-desc">
                Configure your farm location, crop, and soil parameters on the left panel. AgriMind will coordinate specialist meteorology, soil, disease, and market agents to generate an authoritative recommendation.
              </p>
            </div>
          )}

          {/* Result Loaded: Render based on active view */}
          {result && !loading && (
            <>
              {/* Context Summary Chips Card */}
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
                <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
                  {/* HERO: WHAT IS HAPPENING? */}
                  <AdvisoryHero
                    recommendation={result.recommendation}
                    explanation={result.explanation}
                    confidence={result.confidence}
                    disease={result.disease}
                    weatherRisk={result.weather_risk}
                    soilStatus={result.soil_nutrient_status}
                    onScrollToAction={scrollToActions}
                  />

                  {/* ACTION CARD: WHAT SHOULD I DO? (NOW, NEXT, THEN) */}
                  <ActionPlan
                    recommendation={result.recommendation}
                    crop={activeScenario.crop}
                    disease={result.disease}
                    soil={result.soil}
                    weather={result.weather}
                  />

                  {/* DECISION SIGNALS (Weather, Soil, Disease, Market) */}
                  <DecisionSignals
                    weather={result.weather}
                    soil={result.soil}
                    disease={result.disease}
                    market={result.market}
                  />

                  {/* WHY THIS DECISION? (Explanation) */}
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

                  {/* WHAT WOULD CHANGE THIS DECISION? (Explainability Triggers) */}
                  <DecisionChangeTriggers
                    triggers={result.decision_change_triggers}
                    reEvaluationTrigger={result.re_evaluation_trigger}
                    recommendation={result.recommendation}
                  />

                  {/* DISEASE MANAGEMENT (Separated from Fertilizer) */}
                  {result.disease && (
                    <DiseaseActionCard
                      disease={result.disease}
                      crop={activeScenario.crop}
                    />
                  )}

                  {/* NUTRIENT SUPPORT (Separated from Disease Control) */}
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

                  {/* NEARBY AGRICULTURAL STORES (Zero Fabrication) */}
                  <NearbyStoresCard
                    locationName={result.location?.location_name || activeScenario.locationName}
                    coordinates={{
                      lat: result.location?.latitude ?? activeScenario.lat,
                      lon: result.location?.longitude ?? activeScenario.lon,
                    }}
                    stores={[]}
                  />

                  {/* INPUT PRICE & MRP TRANSPARENCY */}
                  <PriceCard
                    crop={activeScenario.crop}
                    mandiPrice={result.market?.current_price || (activeScenario.npk ? Number(result.market?.market_score ? 2200 : 0) : null)}
                    marketScore={result.market?.market_score}
                    marketSignal={result.market?.signal}
                  />

                  {/* HOW AGRIMIND REACHED THIS DECISION (Process Path) */}
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

                  {/* FIELD FEEDBACK LOOP */}
                  <FeedbackCard
                    runId={result.run_id}
                    onFeedbackSubmit={handleFeedbackSubmit}
                  />
                </div>
              )}

              {/* VIEW 2: EVIDENCE & AUDIT (Deep Observability) */}
              {activeView === 'evidence' && (
                <AuditPanel result={result} />
              )}
            </>
          )}
        </section>
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
