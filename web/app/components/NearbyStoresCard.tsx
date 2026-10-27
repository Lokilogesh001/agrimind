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
            <Store size={18} color="var(--forest-dark)" />
            <h3 style={{ fontSize: '15px', margin: 0, fontWeight: 700, letterSpacing: '0.02em' }}>
              NEARBY AGRICULTURAL INPUT STORES
            </h3>
          </div>
          <p style={{ margin: '3px 0 0 26px', fontSize: '12px', color: 'var(--text-secondary)' }}>
            Verified businesses near your farm location
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Radius selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11.5px', color: 'var(--text-muted)' }}>
            <Compass size={13} color="var(--forest-dark)" />
            <span>Radius:</span>
            <select
              value={radius}
              onChange={(e) => handleRadiusChange(Number(e.target.value))}
              disabled={loading}
              className="select"
              style={{
                fontSize: '11.5px',
                padding: '3px 8px',
                width: 'auto',
                borderRadius: 'var(--radius-sm)',
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
                : 'NO STORES'
            }
            variant={stores.length > 0 ? 'success' : 'neutral'}
            size="sm"
          />
        </div>
      </div>

      <div className="card-body">
        {/* Farm Location Info Bar */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--bg-surface-soft)',
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '16px',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
            <MapPin size={14} color="var(--forest-dark)" />
            <span>
              Searching near: <strong style={{ color: 'var(--text-primary)' }}>{locationName || 'Current Farm Location'}</strong>
              {hasCoordinates && (
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '6px' }}>
                  ({coordinates!.lat!.toFixed(4)}°, {coordinates!.lon!.toFixed(4)}°)
                </span>
              )}
            </span>
          </div>

          <button
            onClick={() => handleRadiusChange(radius)}
            disabled={loading}
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '11px', padding: '3px 8px', gap: '4px' }}
            type="button"
          >
            <RefreshCw size={11} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        {/* LOADING STATE */}
        {loading && (
          <div
            style={{
              padding: '28px 16px',
              textAlign: 'center',
              background: 'var(--bg-surface-soft)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-color)',
            }}
          >
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--forest-dark)', fontWeight: 600, fontSize: '13.5px', marginBottom: '8px' }}>
              <div className="spinner" style={{ width: '16px', height: '16px' }} />
              <span>Finding nearby agricultural input stores...</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '320px', margin: '0 auto' }}>
              <div>Location resolved ✓</div>
              <div>Searching verified agricultural businesses...</div>
              <div>Retrieving contact & location coordinates...</div>
            </div>
          </div>
        )}

        {/* API ERROR / FAILURE STATE */}
        {!loading && apiError && (
          <div
            style={{
              textAlign: 'center',
              padding: '24px 16px',
              background: 'var(--bg-surface-soft)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <AlertCircle size={24} color="var(--semantic-warning-text)" style={{ margin: '0 auto 8px' }} />
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
                  padding: '16px',
                  background: 'var(--bg-surface-soft)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  transition: 'border-color 0.15s ease',
                }}
              >
                {/* Header: Store Name, Distance & Verified Badge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '14.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {store.name}
                      </span>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontSize: '10.5px',
                          padding: '2px 7px',
                          borderRadius: '10px',
                          background: 'var(--semantic-success-bg)',
                          border: '1px solid var(--semantic-success-border)',
                          color: 'var(--semantic-success-text)',
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
                        color: 'var(--forest-dark)',
                        background: 'var(--forest-tint)',
                        border: '1px solid var(--forest-tint-border)',
                        padding: '3px 10px',
                        borderRadius: 'var(--radius-pill)',
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
                    <MapPin size={13} color="var(--forest-dark)" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <span>{store.address}</span>
                  </div>
                )}

                {/* Metadata: Phone, Opening Hours, Rating */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {store.phone && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <Phone size={12} color="var(--forest-dark)" />
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Star size={12} fill="#F59E0B" color="#F59E0B" />
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{store.rating.toFixed(1)}</span>
                    </div>
                  )}
                </div>

                {/* Stock & Price Verification Badges */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '8px 12px',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '11px',
                    color: 'var(--text-secondary)',
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Product availability:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>
                      {store.product_stock || 'Not verified'}
                    </strong>
                  </div>
                  <span style={{ color: 'var(--border-color)' }}>•</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Current retailer price:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>
                      {store.retailer_price || 'Not verified'}
                    </strong>
                  </div>
                </div>

                {/* Action Buttons: Call Store, Directions, Website */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                  {store.phone && (
                    <a
                      href={`tel:${store.phone.replace(/\s+/g, '')}`}
                      className="btn btn-outline btn-sm"
                      style={{ padding: '6px 14px', fontSize: '11.5px', gap: '5px' }}
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
                      style={{ padding: '6px 14px', fontSize: '11.5px', gap: '5px' }}
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
                      style={{ padding: '6px 14px', fontSize: '11.5px', gap: '5px' }}
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
              padding: '28px 16px',
              background: 'var(--bg-surface-soft)',
              border: '1px dashed var(--border-color)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <Building size={28} color="var(--forest-dark)" style={{ margin: '0 auto 10px' }} />
            <h4 style={{ fontSize: '14px', color: 'var(--text-primary)', margin: '0 0 6px', fontWeight: 600 }}>
              No verified agricultural input stores were found near this location.
            </h4>
            <div style={{ textAlign: 'left', maxWidth: '380px', margin: '0 auto 14px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <p style={{ margin: '0 0 6px', fontWeight: 600, color: 'var(--text-primary)' }}>Try:</p>
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
              type="button"
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
