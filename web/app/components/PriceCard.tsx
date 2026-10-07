'use client';

import React from 'react';
import { Tag, TrendingUp, AlertCircle, Info, Calendar } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface PriceCardProps {
  crop?: string;
  mandiPrice?: number | null;
  marketScore?: number | null;
  marketSignal?: string | null;
  fertilizerProduct?: string;
}

export function PriceCard({
  crop = 'Crop',
  mandiPrice,
  marketScore,
  marketSignal = 'hold',
  fertilizerProduct,
}: PriceCardProps) {
  const hasMandiPrice = mandiPrice !== undefined && mandiPrice !== null && mandiPrice > 0;

  return (
    <div className="card">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Tag size={17} color="var(--forest-primary)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>PRICE & MRP TRANSPARENCY</h3>
        </div>
        <StatusBadge label="VERIFIED TIERS" variant="mint" size="sm" />
      </div>

      <div className="card-body">
        {/* Mandi Crop Produce Price */}
        <div style={{ marginBottom: '16px', padding: '12px 14px', background: 'var(--bg-surface-soft)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              Crop Produce Market Telemetry
            </span>
            <StatusBadge
              label={hasMandiPrice ? 'OBSERVED PRICE' : 'UNAVAILABLE'}
              variant={hasMandiPrice ? 'success' : 'neutral'}
              size="sm"
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
            <strong style={{ fontSize: '20px', color: 'var(--text-primary)' }}>
              {hasMandiPrice ? `₹${Number(mandiPrice).toLocaleString('en-IN')}` : 'Market data unavailable'}
            </strong>
            {hasMandiPrice && (
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                / quintal ({crop})
              </span>
            )}
          </div>

          <p style={{ margin: '4px 0 0', fontSize: '11.5px', color: 'var(--text-muted)' }}>
            Category: <strong>Observed Mandi Market Rate</strong> (Source: Field input / Agmarknet benchmark). This is distinct from official input MRP.
          </p>
        </div>

        {/* Input Chemical / Fertilizer Price Differentiation Table */}
        <div>
          <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '8px' }}>
            Agrochemical & Nutrient Input Pricing Tiers
          </span>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
            {/* Tier 1: Official MRP */}
            <div style={{ padding: '10px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                Official Statutory MRP
              </span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '3px' }}>
                Official MRP unavailable
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginTop: '3px' }}>
                Statutory subsidized price requires dealer batch check.
              </span>
            </div>

            {/* Tier 2: Seller Price */}
            <div style={{ padding: '10px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                Seller / Retailer Price
              </span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-secondary)', marginTop: '3px' }}>
                Verification required
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginTop: '3px' }}>
                Direct inquiry at local cooperative required.
              </span>
            </div>

            {/* Tier 3: Observed Online Price */}
            <div style={{ padding: '10px 12px', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
              <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                Observed Online Price
              </span>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-secondary)', marginTop: '3px' }}>
                Not available
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', marginTop: '3px' }}>
                Third-party retail aggregator feeds not connected.
              </span>
            </div>
          </div>
        </div>

        <div style={{ marginTop: '12px', fontSize: '11.5px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Info size={13} />
          <span>Never pay above the printed Statutory MRP on licensed seed, fertilizer, or pesticide packaging.</span>
        </div>
      </div>
    </div>
  );
}
