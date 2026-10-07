'use client';

import React from 'react';
import { Store, MapPin, Phone, Navigation, AlertCircle, ExternalLink } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface StoreItem {
  name: string;
  distance_km?: number;
  address?: string;
  phone?: string;
  category?: string;
  verified_stock?: boolean;
}

interface NearbyStoresCardProps {
  locationName: string;
  coordinates?: { lat: number | null; lon: number | null } | null;
  stores?: StoreItem[];
}

export function NearbyStoresCard({
  locationName,
  coordinates,
  stores = [],
}: NearbyStoresCardProps) {
  const hasCoordinates = coordinates && coordinates.lat !== null && coordinates.lon !== null;
  const hasStores = stores && stores.length > 0;

  return (
    <div className="card">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Store size={17} color="var(--forest-primary)" />
          <h3 style={{ fontSize: '15px', margin: 0 }}>NEARBY AGRICULTURAL STORES</h3>
        </div>
        <StatusBadge
          label={hasStores ? `${stores.length} STORES FOUND` : 'VERIFICATION REQUIRED'}
          variant={hasStores ? 'success' : 'neutral'}
          size="sm"
        />
      </div>

      <div className="card-body">
        {/* Farm Location Resolution Context */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', background: 'var(--bg-surface-soft)', borderRadius: 'var(--radius-sm)', marginBottom: '14px', fontSize: '12px', color: 'var(--text-secondary)' }}>
          <MapPin size={14} color="var(--forest-primary)" style={{ flexShrink: 0 }} />
          <span>
            <strong>Location Telemetry:</strong> {locationName || 'Farm location'} {hasCoordinates ? `(${coordinates.lat?.toFixed(4)}°N, ${coordinates.lon?.toFixed(4)}°E)` : '(unresolved coordinates)'}
          </span>
        </div>

        {hasStores ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {stores.map((store, i) => (
              <div key={i} className="store-card">
                <div className="store-card-header">
                  <div>
                    <div className="store-name">{store.name}</div>
                    {store.address && (
                      <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {store.address}
                      </p>
                    )}
                  </div>
                  {store.distance_km !== undefined && (
                    <span className="store-distance">{store.distance_km.toFixed(1)} km</span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginTop: '6px' }}>
                  {store.phone && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <Phone size={12} />
                      <span>{store.phone}</span>
                    </div>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '11px', color: store.verified_stock ? 'var(--semantic-success)' : 'var(--text-muted)' }}>
                      Stock: {store.verified_stock ? 'Verified' : 'Verification required'}
                    </span>
                    {hasCoordinates && (
                      <a
                        href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(store.name + ' ' + (locationName || ''))}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-outline btn-sm"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                      >
                        <Navigation size={11} />
                        <span>Directions</span>
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '18px 12px', background: 'var(--bg-surface-soft)', border: '1px dashed var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
            <AlertCircle size={24} color="var(--text-muted)" style={{ margin: '0 auto 8px' }} />
            <h4 style={{ fontSize: '13.5px', color: 'var(--text-primary)', margin: '0 0 4px' }}>
              No nearby agricultural stores could be verified for this location.
            </h4>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '420px', marginLeft: 'auto', marginRight: 'auto' }}>
              AgriMind does not fabricate retail businesses or input dealer inventories without an authenticated regional cooperative or agro-dealer registry integration. Contact your local Krishi Vigyan Kendra (KVK) or Block Agriculture Office for registered seed and fertilizer stockists.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
