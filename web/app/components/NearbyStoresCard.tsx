'use client';

import React, { useState, useEffect } from 'react';
import {
  Store,
  MapPin,
  Phone,
  Navigation,
  ExternalLink,
  Clock,
  Star,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Compass,
  Building,
} from 'lucide-react';
import { StatusBadge } from './StatusBadge';

export interface VerifiedStoreItem {
  id: string;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  phone?: string | null;
  website?: string | null;
  opening_hours?: string | null;
  rating?: number | null;
  category: string;
  maps_url: string;
  source: string;
  verified: boolean;
  product_stock?: string;
  retailer_price?: string;
}

interface NearbyStoresCardProps {
  locationName: string;
  coordinates?: { lat: number | null; lon: number | null } | null;
  stores?: VerifiedStoreItem[];
}

const RADIUS_OPTIONS = [10, 15, 25, 50];

export function NearbyStoresCard({
  locationName,
  coordinates,
  stores: initialStores = [],
}: NearbyStoresCardProps) {
  const [stores, setStores] = useState<VerifiedStoreItem[]>(initialStores);
  const [radius, setRadius] = useState<number>(15);
  const [loading, setLoading] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const hasCoordinates = Boolean(
    coordinates &&
    coordinates.lat !== null &&
    coordinates.lat !== undefined &&
    coordinates.lon !== null &&
    coordinates.lon !== undefined
  );

  // Sync when initialStores change
  useEffect(() => {
    if (initialStores && initialStores.length > 0) {
      setStores(initialStores);
      setApiError(null);
    }
  }, [initialStores]);

  // Handle radius changes or manual refresh
  const handleRadiusChange = async (newRadius: number) => {
    setRadius(newRadius);
    if (!hasCoordinates && !locationName) return;

    setLoading(true);
    setApiError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const params = new URLSearchParams();
      if (coordinates?.lat !== null && coordinates?.lat !== undefined) {
        params.append('lat', String(coordinates.lat));
      }
      if (coordinates?.lon !== null && coordinates?.lon !== undefined) {
        params.append('lon', String(coordinates.lon));
      }
      if (locationName) {
        params.append('location', locationName);
      }
      params.append('radius', String(newRadius));

      const res = await fetch(`${apiUrl}/api/nearby-stores?${params.toString()}`);
      if (!res.ok) {
        throw new Error('Store discovery service is currently unreachable.');
      }
      const data = await res.json();
      if (data.status === 'unavailable') {
        setApiError(data.message || 'Store discovery is temporarily unavailable.');
        setStores([]);
      } else {
        setStores(data.stores || []);
      }
    } catch (err: any) {
      setApiError('Store discovery is temporarily unavailable. The advisory remains valid.');
      setStores([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header" style={{ flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Store size={18} color="var(--forest-primary)" />
            <h3 style={{ fontSize: '15px', margin: 0, fontWeight: 700, letterSpacing: '0.02em' }}>
              NEARBY AGRICULTURAL INPUT STORES
            </h3>
          </div>
          <p style={{ margin: '3px 0 0 26px', fontSize: '12px', color: 'var(--text-secondary)' }}>
            Verified businesses near your farm location
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Radius selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <Compass size={13} />
            <span>Radius:</span>
            <select
              value={radius}
              onChange={(e) => handleRadiusChange(Number(e.target.value))}
              disabled={loading}
              style={{
                fontSize: '11px',
                padding: '2px 6px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-surface)',
                color: 'var(--text-primary)',
                cursor: 'pointer',
              }}
            >
              {RADIUS_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r} km
                </option>
              ))}
            </select>
          </div>

          <StatusBadge
            label={
              loading
                ? 'SEARCHING...'
                : stores.length > 0
                ? `${stores.length} VERIFIED STORE${stores.length > 1 ? 'S' : ''}`
                : 'NO VERIFIED STORES'
            }
            variant={stores.length > 0 ? 'success' : 'neutral'}
            size="sm"
          />
        </div>
      </div>

      <div className="card-body">
        {/* Farm Location Telemetry (Privacy Protected: Exposes Village / District / State, NOT raw coordinates) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 12px',
            background: 'var(--bg-surface-soft)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '14px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MapPin size={14} color="var(--forest-primary)" style={{ flexShrink: 0 }} />
            <span>
              <strong>Farm Location:</strong> {locationName || 'Farm location registered'}
              {' — '}
              <span style={{ color: 'var(--text-muted)' }}>Search radius: {radius} km</span>
            </span>
          </div>

          <button
            onClick={() => handleRadiusChange(radius)}
            disabled={loading}
            className="btn btn-outline btn-sm"
            style={{ padding: '3px 8px', fontSize: '11px', gap: '4px' }}
            title="Refresh nearby businesses"
          >
            <RefreshCw size={11} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        {/* LOADING STATE */}
        {loading && (
          <div
            style={{
              padding: '24px 16px',
              textAlign: 'center',
              background: 'var(--bg-surface-soft)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-color)',
            }}
          >
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--forest-primary)', fontWeight: 600, fontSize: '13.5px', marginBottom: '8px' }}>
              <RefreshCw size={16} className="spin" />
              <span>Finding nearby agricultural input stores...</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '320px', margin: '0 auto' }}>
              <div>Location resolved ✓</div>
              <div>Searching nearby agricultural businesses...</div>
              <div>Finding verified contact details...</div>
            </div>
          </div>
        )}

        {/* API ERROR / FAILURE STATE */}
        {!loading && apiError && (
          <div
            style={{
              textAlign: 'center',
              padding: '20px 16px',
              background: 'var(--bg-surface-soft)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <AlertCircle size={24} color="#d97706" style={{ margin: '0 auto 8px' }} />
            <h4 style={{ fontSize: '13.5px', color: 'var(--text-primary)', margin: '0 0 4px', fontWeight: 600 }}>
              Store discovery is temporarily unavailable.
            </h4>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
              The advisory remains valid. Check back shortly or contact your local Block Agriculture Office.
            </p>
          </div>
        )}

        {/* VERIFIED STORE LIST */}
        {!loading && !apiError && stores.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {stores.map((store) => (
              <div
                key={store.id}
                style={{
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '14px',
                  background: 'var(--bg-surface)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  transition: 'box-shadow 0.15s ease',
                }}
              >
                {/* Header: Store Name, Distance & Verified Badge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {store.name}
                      </span>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontSize: '10.5px',
                          padding: '1px 6px',
                          borderRadius: '10px',
                          background: 'rgba(22, 101, 52, 0.1)',
                          color: '#15803d',
                          fontWeight: 600,
                        }}
                      >
                        <CheckCircle2 size={11} />
                        Location verified
                      </span>
                    </div>

                    {store.category && (
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {store.category}
                      </div>
                    )}
                  </div>

                  {store.distance_km !== undefined && (
                    <div
                      style={{
                        fontSize: '12px',
                        fontWeight: 700,
                        color: 'var(--forest-primary)',
                        background: 'var(--bg-surface-soft)',
                        padding: '3px 8px',
                        borderRadius: 'var(--radius-sm)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {store.distance_km.toFixed(1)} km from your farm
                    </div>
                  )}
                </div>

                {/* Address */}
                {store.address && (
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <MapPin size={13} color="var(--text-muted)" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <span>{store.address}</span>
                  </div>
                )}

                {/* Metadata: Phone, Opening Hours, Rating (Only displayed if provided by verified source) */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {store.phone && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <Phone size={12} color="var(--forest-primary)" />
                      <span>{store.phone}</span>
                    </div>
                  )}

                  {store.opening_hours && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <Clock size={12} color="var(--text-muted)" />
                      <span>{store.opening_hours}</span>
                    </div>
                  )}

                  {store.rating !== null && store.rating !== undefined && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <Star size={12} fill="#eab308" color="#eab308" />
                      <span style={{ fontWeight: 600 }}>{store.rating.toFixed(1)}</span>
                    </div>
                  )}
                </div>

                {/* Stock & Price Verification Badges (Mandatory: Zero Fabrication) */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '6px 10px',
                    background: 'var(--bg-surface-soft)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '11px',
                    color: 'var(--text-secondary)',
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Product availability:</span>
                    <strong style={{ color: 'var(--text-secondary)' }}>
                      {store.product_stock || 'Not verified'}
                    </strong>
                  </div>
                  <span style={{ color: 'var(--border-color)' }}>•</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Current retailer price:</span>
                    <strong style={{ color: 'var(--text-secondary)' }}>
                      {store.retailer_price || 'Not verified'}
                    </strong>
                  </div>
                </div>

                {/* Action Buttons: Call Store, Directions, Website */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '2px' }}>
                  {store.phone && (
                    <a
                      href={`tel:${store.phone.replace(/\s+/g, '')}`}
                      className="btn btn-outline btn-sm"
                      style={{ padding: '5px 12px', fontSize: '11.5px', gap: '5px' }}
                    >
                      <Phone size={12} />
                      <span>Call Store</span>
                    </a>
                  )}

                  {store.maps_url && (
                    <a
                      href={store.maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-primary btn-sm"
                      style={{ padding: '5px 12px', fontSize: '11.5px', gap: '5px' }}
                    >
                      <Navigation size={12} />
                      <span>Directions</span>
                    </a>
                  )}

                  {store.website && (
                    <a
                      href={store.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-outline btn-sm"
                      style={{ padding: '5px 12px', fontSize: '11.5px', gap: '5px' }}
                    >
                      <ExternalLink size={12} />
                      <span>Visit Website</span>
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* EMPTY RESULTS STATE */}
        {!loading && !apiError && stores.length === 0 && (
          <div
            style={{
              textAlign: 'center',
              padding: '24px 16px',
              background: 'var(--bg-surface-soft)',
              border: '1px dashed var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <Building size={28} color="var(--text-muted)" style={{ margin: '0 auto 10px' }} />
            <h4 style={{ fontSize: '14px', color: 'var(--text-primary)', margin: '0 0 6px', fontWeight: 600 }}>
              No verified agricultural input stores were found near this location.
            </h4>
            <div style={{ textAlign: 'left', maxWidth: '380px', margin: '0 auto 14px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <p style={{ margin: '0 0 6px', fontWeight: 600 }}>Try:</p>
              <ul style={{ margin: 0, paddingLeft: '20px', lineHeight: 1.6 }}>
                <li>expanding the search radius using the dropdown above</li>
                <li>checking the local Krishi Vigyan Kendra (KVK)</li>
                <li>checking the Block Agriculture Office</li>
                <li>contacting a registered local agricultural cooperative</li>
              </ul>
            </div>
            <button
              onClick={() => handleRadiusChange(Math.min(50, radius + 15))}
              className="btn btn-outline btn-sm"
              style={{ fontSize: '11.5px', gap: '5px' }}
            >
              <Compass size={12} />
              <span>Expand search to {Math.min(50, radius + 15)} km</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
