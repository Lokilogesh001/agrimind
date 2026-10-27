'use client';

import React from 'react';
import { Tag, TrendingUp, AlertCircle, Info, Calendar, Scale, HelpCircle } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface PriceCardProps {
  crop?: string;
  benchmarkPrice?: number | null;
  observedPrice?: number | null;
  mandiPrice?: number | null; // Backwards-compatible
  mandiName?: string;
  commodityGrade?: string;
  retrievalTimestamp?: string;
  marketScore?: number | null;
  marketSignal?: string | null;
  marketFormula?: string;
  phenologyNote?: string;
  fertilizerProduct?: string;
}

export function PriceCard({
  crop = 'Crop',
  benchmarkPrice,
  observedPrice,
  mandiPrice,
  mandiName = 'Local Mandi / Agmarknet APMC',
  commodityGrade = 'FAQ (Fair Average Quality)',
  retrievalTimestamp,
  marketScore,
  marketSignal = 'hold',
  marketFormula,
  phenologyNote,
  fertilizerProduct,
}: PriceCardProps) {
  // Strictly isolate farmer entered benchmark from externally observed APMC mandi rate
  const finalObserved = (observedPrice !== undefined && observedPrice !== null && Number(observedPrice) > 0)
    ? Number(observedPrice)
    : null;
  const finalBenchmark = (benchmarkPrice !== undefined && benchmarkPrice !== null && Number(benchmarkPrice) > 0)
    ? Number(benchmarkPrice)
    : (mandiPrice !== undefined && mandiPrice !== null && Number(mandiPrice) > 0 ? Number(mandiPrice) : null);

  const hasObserved = finalObserved !== null;
  const hasBenchmark = finalBenchmark !== null;

  return (
    <div className="card" id="price-card-section">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Tag size={18} color="var(--forest-dark)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>PRICE PROVENANCE & MRP TRANSPARENCY</h3>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          {hasBenchmark && (
            <StatusBadge label="USER INPUT" variant="neutral" size="sm" />
          )}
          {hasObserved && (
            <StatusBadge label="AGMARKNET RATE" variant="mint" size="sm" />
          )}
        </div>
      </div>

      <div className="card-body">
        {/* Mandi Crop Produce Price Provenance Grid */}
        <div style={{ marginBottom: '18px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
          
          {/* Card 1: Farmer-Entered Benchmark Rate */}
          <div style={{ padding: '14px 16px', background: 'var(--bg-surface-soft)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                Farmer-Entered Benchmark
              </span>
              <StatusBadge
                label={hasBenchmark ? 'DECLARED' : 'NOT ENTERED'}
                variant={hasBenchmark ? 'neutral' : 'neutral'}
                size="sm"
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '4px 0' }}>
              <strong style={{ fontSize: '22px', color: 'var(--text-primary)', fontWeight: 800 }}>
                {hasBenchmark ? `₹${Number(finalBenchmark).toLocaleString('en-IN')}` : 'No benchmark entered'}
              </strong>
              {hasBenchmark && (
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  / quintal ({crop})
                </span>
              )}
            </div>

            <p style={{ margin: '6px 0 0', fontSize: '11.5px', color: 'var(--text-muted)', lineHeight: '1.45' }}>
              Provenance: <strong>Farmer Direct Input</strong>. Declared reference expectation prior to harvesting.
            </p>
          </div>

          {/* Card 2: Externally Observed Mandi Modal Rate */}
          <div style={{ padding: '14px 16px', background: hasObserved ? 'var(--forest-tint)' : 'var(--bg-surface-soft)', borderRadius: 'var(--radius-sm)', border: hasObserved ? '1px solid var(--forest-tint-border)' : '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                Observed Mandi Modal Rate
              </span>
              <StatusBadge
                label={hasObserved ? 'OBSERVED APMC' : 'PENDING TELEMETRY'}
                variant={hasObserved ? 'success' : 'neutral'}
                size="sm"
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '4px 0' }}>
              <strong style={{ fontSize: '22px', color: 'var(--text-primary)', fontWeight: 800 }}>
                {hasObserved ? `₹${Number(finalObserved).toLocaleString('en-IN')}` : 'Mandi feed unavailable'}
              </strong>
              {hasObserved && (
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  / quintal ({crop})
                </span>
              )}
            </div>

            <div style={{ margin: '6px 0 0', fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: '1.45' }}>
              <div>Market: <strong style={{ color: 'var(--text-primary)' }}>{mandiName}</strong> · Grade: <strong>{commodityGrade}</strong></div>
              {retrievalTimestamp && (
                <div style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                  Retrieved: {retrievalTimestamp}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Market Signal Logic & Phenology Guard */}
        <div style={{ marginBottom: '18px', padding: '14px 16px', background: 'var(--bg-surface-soft)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={16} color="var(--forest-dark)" />
              <span style={{ fontSize: '12.5px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                Market Advisory Signal: <strong style={{ color: 'var(--text-primary)' }}>{(marketSignal || 'HOLD').toUpperCase()}</strong> (Score: {marketScore ? (marketScore * 100).toFixed(1) + '%' : 'N/A'})
              </span>
            </div>
            {phenologyNote && (
              <StatusBadge label="PHENOLOGY GUARD" variant="warning" size="sm" />
            )}
          </div>

          {phenologyNote ? (
            <div style={{ padding: '10px 12px', background: 'var(--semantic-warning-bg)', border: '1px solid var(--semantic-warning-border)', borderLeftWidth: '3px', borderLeftColor: 'var(--semantic-warning)', borderRadius: 'var(--radius-sm)', fontSize: '12.5px', color: 'var(--semantic-warning-text)', marginBottom: '8px', lineHeight: 1.5 }}>
              <strong>Stage Guard:</strong> {phenologyNote}
            </div>
          ) : (
            <p style={{ margin: '0 0 8px', fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Directional dispatch advisory evaluated across commodity arrivals, price velocity, and perishable shelf-life.
            </p>
          )}

          {marketFormula && (
            <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', background: 'var(--bg-surface)', padding: '6px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
              Formula: {marketFormula}
            </div>
          )}
        </div>

        {/* Input Chemical / Fertilizer Price Differentiation Table */}
        <div>
          <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', display: 'block', marginBottom: '8px', letterSpacing: '0.04em' }}>
            Agrochemical & Nutrient Input Pricing Tiers
          </span>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
            {/* Tier 1: Official MRP */}
            <div style={{ padding: '12px 14px', background: 'var(--bg-surface-soft)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                Official Statutory MRP
              </span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '3px' }}>
                Official MRP on Bag
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginTop: '3px', lineHeight: 1.4 }}>
                Statutory subsidized price printed on fertilizer bag.
              </span>
            </div>

            {/* Tier 2: Seller Price */}
            <div style={{ padding: '12px 14px', background: 'var(--bg-surface-soft)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                Seller / Retailer Price
              </span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--forest-dark)', marginTop: '3px' }}>
                Dealer Quote Required
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginTop: '3px', lineHeight: 1.4 }}>
                Local PACS cooperative or licensed agro-dealer quote.
              </span>
            </div>

            {/* Tier 3: Observed Online Price */}
            <div style={{ padding: '12px 14px', background: 'var(--bg-surface-soft)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                Observed Online Price
              </span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', marginTop: '3px' }}>
                Not connected
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginTop: '3px', lineHeight: 1.4 }}>
                Third-party retail aggregator feeds not connected.
              </span>
            </div>
          </div>
        </div>

        <div style={{ marginTop: '14px', fontSize: '11.5px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Info size={14} color="var(--forest-dark)" style={{ flexShrink: 0 }} />
          <span>Statutory Notice: Under Essential Commodities Act / FCO, dealers cannot charge above printed MRP.</span>
        </div>
      </div>
    </div>
  );
}
