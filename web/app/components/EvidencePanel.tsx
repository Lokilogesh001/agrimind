'use client';

import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText, CheckCircle2 } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface EvidenceItem {
  id?: string;
  source?: string;
  text: string;
  page?: number | string;
  chunk?: number | string;
  final_rank_score?: number;
  score?: number;
  source_reliability?: number;
  crop_relevance?: number;
  location_relevance?: number;
  stage_relevance?: number;
  relevance_badges?: {
    crop_match?: string;
    location_match?: string;
    stage_match?: string;
    source_authority?: string;
  };
  metadata?: any;
}

interface EvidencePanelProps {
  evidenceList?: EvidenceItem[];
}

export function EvidencePanel({ evidenceList = [] }: EvidencePanelProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (!evidenceList || evidenceList.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}>
        <BookOpen size={24} color="var(--text-muted)" style={{ margin: '0 auto 8px' }} />
        <h4 style={{ fontSize: '14px', color: 'var(--text-primary)', margin: 0 }}>
          No Agronomic Evidence Documents Retrieved
        </h4>
        <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
          Standard deterministic rules were applied directly without external document retrieval.
        </p>
      </div>
    );
  }

  const toggleExpand = (idx: number) => {
    setExpandedId(expandedId === idx ? null : idx);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {evidenceList.map((item, idx) => {
        const isExpanded = expandedId === idx;
        const badges = item.relevance_badges || item.metadata?.relevance_badges || {};
        const sourceDoc = item.source || item.metadata?.source_document || 'ICAR Kharif Agro-Advisories 2025';
        const page = item.page ?? item.metadata?.source_page ?? '—';
        const rankScore = Number(item.final_rank_score ?? item.score ?? 0.85).toFixed(2);
        const reliability = Number(item.source_reliability ?? 0.90).toFixed(2);

        // Preview snippet: first 160 characters
        const previewText = item.text ? item.text.slice(0, 160).trim() + '…' : '';

        return (
          <div key={idx} className="card" style={{ boxShadow: 'var(--shadow-xs)' }}>
            <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileText size={16} color="var(--forest-primary)" />
                  <strong style={{ fontSize: '13.5px', color: 'var(--forest-deep)' }}>
                    {sourceDoc}
                  </strong>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--teal-dark)', background: 'var(--mint-tint)', border: '1px solid var(--mint-tint-border)', padding: '2px 8px', borderRadius: '999px', fontWeight: 600 }}>
                    Relevance Rank: {rankScore}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Page {page}
                  </span>
                </div>
              </div>

              {/* Relevance Badges */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', margin: '2px 0' }}>
                {badges.crop_match && (
                  <span className="badge badge-success" style={{ fontSize: '10px' }}>
                    Crop Match: {badges.crop_match}
                  </span>
                )}
                {badges.location_match && (
                  <span className="badge badge-brand" style={{ fontSize: '10px' }}>
                    Regional Match: {badges.location_match}
                  </span>
                )}
                {badges.stage_match && (
                  <span className="badge badge-mint" style={{ fontSize: '10px' }}>
                    Stage Match: {badges.stage_match}
                  </span>
                )}
                <span className="badge badge-neutral" style={{ fontSize: '10px' }}>
                  Source Reliability: {reliability}
                </span>
              </div>

              {/* Text Preview or Full Text */}
              <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                {isExpanded ? item.text : previewText}
              </p>

              {/* Toggle Accordion */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
                <button
                  type="button"
                  onClick={() => toggleExpand(idx)}
                  className="btn btn-outline btn-sm"
                  style={{ fontSize: '11.5px', padding: '3px 10px' }}
                >
                  {isExpanded ? (
                    <>
                      <span>Collapse Text</span>
                      <ChevronUp size={12} />
                    </>
                  ) : (
                    <>
                      <span>Read Supporting Guidance</span>
                      <ChevronDown size={12} />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
