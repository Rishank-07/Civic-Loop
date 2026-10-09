import React, { useState } from 'react';

interface NewCaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    title: string;
    issue_category: 'GARBAGE' | 'DRAINAGE' | 'OTHER';
    location_text: string;
    ward: string;
    jurisdiction: string;
    initial_complaint_raw_text?: string;
  }) => Promise<void>;
}

export const NewCaseModal: React.FC<NewCaseModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<'GARBAGE' | 'DRAINAGE' | 'OTHER'>('GARBAGE');
  const [locationText, setLocationText] = useState('');
  const [ward, setWard] = useState('Ward 150 - Bellandur');
  const [jurisdiction, setJurisdiction] = useState('BBMP Mahadevapura Zone');
  const [complaintText, setComplaintText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit({
        title,
        issue_category: category,
        location_text: locationText,
        ward,
        jurisdiction,
        initial_complaint_raw_text: complaintText || undefined,
      });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to lodge case');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.7)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '20px',
    }}>
      <div className="glass-card" style={{
        maxWidth: '560px',
        width: '100%',
        padding: '28px',
        maxHeight: '90vh',
        overflowY: 'auto',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
              Report Civic Problem
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Intake for Bengaluru garbage blackspots or blocked SWD drains.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-dim)',
              fontSize: '1.2rem',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div style={{
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: '8px',
            padding: '10px 14px',
            color: '#fb7185',
            fontSize: '0.82rem',
            marginBottom: '16px',
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Case Title *
            </label>
            <input
              className="input-field"
              required
              placeholder="e.g. Blocked culvert causing knee-deep water on 100ft road"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                Category *
              </label>
              <select
                className="input-field"
                value={category}
                onChange={(e) => setCategory(e.target.value as any)}
              >
                <option value="GARBAGE">Garbage Accumulation</option>
                <option value="DRAINAGE">Blocked SWD Drainage</option>
                <option value="OTHER">Other Civic Defect</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                Ward *
              </label>
              <select
                className="input-field"
                value={ward}
                onChange={(e) => setWard(e.target.value)}
              >
                <option value="Ward 150 - Bellandur">Ward 150 - Bellandur</option>
                <option value="Ward 112 - Domlur">Ward 112 - Domlur</option>
                <option value="Ward 174 - HSR Layout">Ward 174 - HSR Layout</option>
                <option value="Ward 80 - Koramangala">Ward 80 - Koramangala</option>
              </select>
            </div>
          </div>

          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Zonal Jurisdiction *
            </label>
            <input
              className="input-field"
              required
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Physical Location & Landmarks *
            </label>
            <input
              className="input-field"
              required
              placeholder="e.g. Near 4th Cross SWD culvert, behind public school"
              value={locationText}
              onChange={(e) => setLocationText(e.target.value)}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Initial Complaint Description (Ground Truth)
            </label>
            <textarea
              className="input-field"
              rows={3}
              placeholder="Describe physical condition, accumulation size, hazards, or BBMP ticket number if any..."
              value={complaintText}
              onChange={(e) => setComplaintText(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Registering...' : 'Submit to CivicLoop'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
