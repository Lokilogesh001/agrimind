'use client';

import React from 'react';
import { Sprout, Activity, Database, ShieldCheck, Wifi, WifiOff } from 'lucide-react';

interface HeaderProps {
  activeView: 'farmer' | 'evidence';
  onViewChange: (view: 'farmer' | 'evidence') => void;
  apiConnected?: boolean;
}

export function Header({ activeView, onViewChange, apiConnected = true }: HeaderProps) {
  return (
    <header className="top-header" role="banner">
      <div className="brand-section">
        <div className="brand-icon-wrapper" aria-hidden="true">
          <Sprout size={26} />
        </div>
        <div>
          <div className="eyebrow">
            <ShieldCheck size={12} />
            Observable Multi-Agent Agronomy
          </div>
          <h1 className="brand-title">AgriMind</h1>
          <p className="brand-subtitle">
            Intelligent Crop Advisory & Autonomous Agricultural Decision Support
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div
          className="header-status-badge"
          title={apiConnected ? 'AgriMind multi-agent reasoning cluster is operational' : 'AgriMind backend unreachable'}
          style={!apiConnected ? { borderColor: 'var(--semantic-warning-border)', background: 'var(--semantic-warning-bg)', color: 'var(--semantic-warning-text)' } : {}}
        >
          <span
            className="status-dot"
            aria-hidden="true"
            style={!apiConnected ? { backgroundColor: 'var(--semantic-warning)', boxShadow: '0 0 0 2px rgba(245, 158, 11, 0.35)' } : {}}
          />
          <span>{apiConnected ? 'Advisory Engine Ready' : 'Backend Disconnected'}</span>
        </div>

        <nav className="tabs-nav" role="tablist" aria-label="Advisory Display Mode">
          <button
            role="tab"
            aria-selected={activeView === 'farmer'}
            className={`tab-btn ${activeView === 'farmer' ? 'active' : ''}`}
            onClick={() => onViewChange('farmer')}
            id="tab-farmer-view"
            type="button"
          >
            <Activity size={15} />
            <span>Advisory</span>
          </button>
          <button
            role="tab"
            aria-selected={activeView === 'evidence'}
            className={`tab-btn ${activeView === 'evidence' ? 'active' : ''}`}
            onClick={() => onViewChange('evidence')}
            id="tab-evidence-view"
            type="button"
          >
            <Database size={15} />
            <span>Evidence & Audit</span>
          </button>
        </nav>
      </div>
    </header>
  );
}
