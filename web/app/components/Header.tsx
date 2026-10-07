'use client';

import React from 'react';
import { Sprout, Activity, Database, CheckCircle2 } from 'lucide-react';

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
          <Sprout size={24} />
        </div>
        <div>
          <div className="eyebrow">Observable Multi-Agent Agronomy</div>
          <h1 className="brand-title">AgriMind</h1>
          <p className="brand-subtitle">
            Intelligent Crop Advisory & Autonomous Agricultural Decision Support
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
        <div className="header-status-badge" title="AgriMind multi-agent reasoning cluster is operational">
          <span className="status-dot" aria-hidden="true" />
          <span>Advisory Engine Ready</span>
        </div>

        <div className="tabs-nav" role="tablist" aria-label="Advisory Display Mode">
          <button
            role="tab"
            aria-selected={activeView === 'farmer'}
            className={`tab-btn ${activeView === 'farmer' ? 'active' : ''}`}
            onClick={() => onViewChange('farmer')}
            id="tab-farmer-view"
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
          >
            <Database size={15} />
            <span>Evidence & Audit</span>
          </button>
        </div>
      </div>
    </header>
  );
}
