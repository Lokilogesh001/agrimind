'use client';

import React, { useState, useEffect } from 'react';
import { CloudSun, Sprout, ShieldAlert, TrendingUp, Compass, CheckCircle2 } from 'lucide-react';

interface OrchestrationLoaderProps {
  hasImage?: boolean;
}

export function OrchestrationLoader({ hasImage = false }: OrchestrationLoaderProps) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t1 = setTimeout(() => setStep(1), 350);
    const t2 = setTimeout(() => setStep(2), 700);
    const t3 = setTimeout(() => setStep(3), 1100);
    const t4 = setTimeout(() => setStep(4), 1500);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, []);

  const agents = [
    {
      name: 'Weather Agent',
      desc: 'Retrieving meteorological radar & precipitation risk',
      icon: <CloudSun size={17} color="var(--semantic-info)" />,
      doneAt: 0,
    },
    {
      name: 'Soil Agent',
      desc: 'Evaluating nutrient targets & deficiency thresholds',
      icon: <Sprout size={17} color="var(--forest-dark)" />,
      doneAt: 1,
    },
    {
      name: 'Disease Agent',
      desc: hasImage ? 'Running PyTorch vision disease classification' : 'Checking baseline phytosanitary indicators',
      icon: <ShieldAlert size={17} color="var(--semantic-danger)" />,
      doneAt: 2,
    },
    {
      name: 'Market Intelligence Agent',
      desc: 'Analyzing mandi price momentum & selling window',
      icon: <TrendingUp size={17} color="var(--teal-dark)" />,
      doneAt: 3,
    },
    {
      name: 'Advisory Engine & Safety Guard',
      desc: 'Applying deterministic agronomic safety rules & conflict policy',
      icon: <Compass size={17} color="var(--forest-dark)" />,
      doneAt: 4,
    },
  ];

  return (
    <div className="card" style={{ padding: '32px 24px', textAlign: 'center' }}>
      <div style={{ maxWidth: '480px', margin: '0 auto' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '52px', height: '52px', borderRadius: '50%', background: 'var(--forest-tint)', border: '1px solid var(--forest-tint-border)', color: 'var(--forest-dark)', marginBottom: '14px' }}>
          <div className="spinner" style={{ width: '24px', height: '24px', borderWidth: '3px' }} />
        </div>

        <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px' }}>
          AgriMind Orchestration in Progress
        </h3>
        <p style={{ margin: '0 0 22px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          Executing LangGraph multi-agent pipeline with deterministic safety verification…
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', textAlign: 'left' }}>
          {agents.map((ag, i) => {
            const isCompleted = step > ag.doneAt;
            const isRunning = step === ag.doneAt;

            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-sm)',
                  background: isRunning ? 'var(--forest-tint)' : 'var(--bg-surface-soft)',
                  border: `1px solid ${isRunning ? 'var(--forest-soft)' : 'var(--border-subtle)'}`,
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {ag.icon}
                  <div>
                    <strong style={{ fontSize: '13px', color: 'var(--text-primary)', display: 'block' }}>
                      {ag.name}
                    </strong>
                    <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {ag.desc}
                    </span>
                  </div>
                </div>

                <div style={{ flexShrink: 0 }}>
                  {isCompleted ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11.5px', color: 'var(--forest-dark)', fontWeight: 700 }}>
                      <CheckCircle2 size={14} />
                      Completed
                    </span>
                  ) : isRunning ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '11.5px', color: 'var(--forest-dark)', fontWeight: 600 }}>
                      <div className="spinner" style={{ width: '12px', height: '12px' }} />
                      Analyzing
                    </span>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Waiting
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
