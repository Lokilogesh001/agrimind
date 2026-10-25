'use client';

import React, { useState } from 'react';
import { MessageSquare, ThumbsUp, ThumbsDown, HelpCircle, Check, Send } from 'lucide-react';

interface FeedbackCardProps {
  runId: string;
  onFeedbackSubmit: (feedback: {
    run_id: string;
    farmer_action_taken: string;
    outcome_reported: string;
    comment: string;
    days_post_application?: number;
    reporter_type?: string;
    outcome_category?: string;
  }) => Promise<boolean>;
}

export function FeedbackCard({ runId, onFeedbackSubmit }: FeedbackCardProps) {
  const [rating, setRating] = useState<'yes' | 'partially' | 'no' | null>(null);
  const [actionTaken, setActionTaken] = useState('');
  const [outcomeReported, setOutcomeReported] = useState('');
  const [comment, setComment] = useState('');
  const [daysPostApp, setDaysPostApp] = useState('3');
  const [reporterType, setReporterType] = useState('farmer_self_report');
  const [outcomeCategory, setOutcomeCategory] = useState('positive_improvement');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actionTaken.trim()) {
      setError('Please mention the action taken in the field.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const success = await onFeedbackSubmit({
        run_id: runId,
        farmer_action_taken: `${rating ? `[Rating: ${rating.toUpperCase()}] ` : ''}${actionTaken}`,
        outcome_reported: outcomeReported,
        comment,
        days_post_application: Number(daysPostApp) || 3,
        reporter_type: reporterType,
        outcome_category: outcomeCategory,
      });
      if (success) {
        setSubmitted(true);
      }
    } catch (err: any) {
      setError(err?.message || 'Error saving feedback');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="card" style={{ padding: '20px', textAlign: 'center', background: 'var(--semantic-success-bg)', border: '1px solid var(--semantic-success-border)' }}>
        <Check size={28} color="var(--semantic-success)" style={{ margin: '0 auto 6px' }} />
        <h4 style={{ fontSize: '14px', color: 'var(--semantic-success-text)', margin: '0 0 4px' }}>
          Thank You for Closing the Feedback Loop!
        </h4>
        <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--semantic-success-text)' }}>
          Your field observation has been logged to the AgriMind continuous agronomic audit registry (Run ID: {runId}).
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header" style={{ padding: '12px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <MessageSquare size={16} color="var(--forest-primary)" />
          <h3 style={{ fontSize: '14px', margin: 0 }}>WAS THIS ADVISORY USEFUL?</h3>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            type="button"
            className={`btn btn-sm ${rating === 'yes' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '4px 8px', fontSize: '11px' }}
            onClick={() => setRating('yes')}
          >
            <ThumbsUp size={12} />
            <span>Yes</span>
          </button>
          <button
            type="button"
            className={`btn btn-sm ${rating === 'partially' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '4px 8px', fontSize: '11px' }}
            onClick={() => setRating('partially')}
          >
            <HelpCircle size={12} />
            <span>Partially</span>
          </button>
          <button
            type="button"
            className={`btn btn-sm ${rating === 'no' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '4px 8px', fontSize: '11px' }}
            onClick={() => setRating('no')}
          >
            <ThumbsDown size={12} />
            <span>No</span>
          </button>
        </div>
      </div>

      <div className="card-body" style={{ padding: '14px 18px' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div>
            <label className="form-label" style={{ fontSize: '12px' }}>
              Field Action Taken by Farmer *
            </label>
            <input
              className="input"
              style={{ fontSize: '12.5px', padding: '7px 10px' }}
              placeholder="e.g. Sprayed recommended fungicide; deferred fertilizer due to rain"
              value={actionTaken}
              onChange={e => setActionTaken(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
            <div>
              <label className="form-label" style={{ fontSize: '12px' }}>
                Reporter Verification Role
              </label>
              <select
                className="input"
                style={{ fontSize: '12px', padding: '7px 8px' }}
                value={reporterType}
                onChange={e => setReporterType(e.target.value)}
              >
                <option value="farmer_self_report">Farmer Self-Report</option>
                <option value="extension_worker">Agricultural Extension Officer</option>
                <option value="kvk_agronomist">KVK Agronomist / Scientist</option>
              </select>
            </div>

            <div>
              <label className="form-label" style={{ fontSize: '12px' }}>
                Follow-Up Interval
              </label>
              <select
                className="input"
                style={{ fontSize: '12px', padding: '7px 8px' }}
                value={daysPostApp}
                onChange={e => setDaysPostApp(e.target.value)}
              >
                <option value="1">1 Day (Immediate response)</option>
                <option value="3">3 Days (Early check)</option>
                <option value="7">7 Days (Full cycle evaluation)</option>
                <option value="14">14 Days (Phenological progress)</option>
              </select>
            </div>

            <div>
              <label className="form-label" style={{ fontSize: '12px' }}>
                Outcome Classification
              </label>
              <select
                className="input"
                style={{ fontSize: '12px', padding: '7px 8px' }}
                value={outcomeCategory}
                onChange={e => setOutcomeCategory(e.target.value)}
              >
                <option value="positive_improvement">Positive Improvement</option>
                <option value="no_change_neutral">No Observable Change</option>
                <option value="phytotoxicity_negative">Phytotoxicity / Adverse</option>
                <option value="unobserved">Pending Field Visit</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
            <div>
              <label className="form-label" style={{ fontSize: '12px' }}>
                Observed Crop Outcome [Optional]
              </label>
              <input
                className="input"
                style={{ fontSize: '12.5px', padding: '7px 10px' }}
                placeholder="e.g. Leaf spot halted; foliage greening observed"
                value={outcomeReported}
                onChange={e => setOutcomeReported(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label" style={{ fontSize: '12px' }}>
                Field Notes & Comments [Optional]
              </label>
              <input
                className="input"
                style={{ fontSize: '12.5px', padding: '7px 10px' }}
                placeholder="e.g. Follow-up soil check in 10 days"
                value={comment}
                onChange={e => setComment(e.target.value)}
              />
            </div>
          </div>

          <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.4', background: 'var(--bg-surface-soft)', padding: '6px 10px', borderRadius: '4px' }}>
            <strong>Research Methodology Notice:</strong> Farmer self-reported outcomes provide valuable qualitative field telemetry. To establish formal causal efficacy, observations undergo verification against weather logs and KVK agronomic trials.
          </div>

          {error && (
            <div style={{ fontSize: '12px', color: 'var(--semantic-danger)', fontWeight: 500 }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
            <button
              type="submit"
              disabled={loading || !actionTaken.trim()}
              className="btn btn-primary btn-sm"
              style={{ padding: '6px 14px' }}
            >
              <Send size={13} />
              <span>{loading ? 'Submitting…' : 'Submit Field Feedback'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
