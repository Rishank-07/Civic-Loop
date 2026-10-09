import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

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
  onLinkToExistingCase?: (targetCaseId: number, explanation: string) => Promise<void>;
}

export const NewCaseModal: React.FC<NewCaseModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  onLinkToExistingCase,
}) => {
  const [activeTab, setActiveTab] = useState<'MANUAL' | 'SMART_EXTRACT'>('SMART_EXTRACT');
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<'GARBAGE' | 'DRAINAGE' | 'OTHER'>('GARBAGE');
  const [locationText, setLocationText] = useState('');
  const [ward, setWard] = useState('Ward 150 - Bellandur');
  const [jurisdiction, setJurisdiction] = useState('BBMP Mahadevapura Zone');
  const [complaintText, setComplaintText] = useState('');

  // AI extraction states
  const [rawInputText, setRawInputText] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionResult, setExtractionResult] = useState<any>(null);
  const [extractError, setExtractError] = useState<string | null>(null);

  // Case linking candidate matches
  const [candidateMatches, setCandidateMatches] = useState<any[]>([]);
  const [isSearchingMatches, setIsSearchingMatches] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);


  // Search for cross-portal duplicates whenever category or location changes
  useEffect(() => {
    if (!locationText || locationText.length < 5) {
      setCandidateMatches([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingMatches(true);
      try {
        const matches = await api.findCaseLinks({
          category,
          location_text: locationText,
          ward,
        });
        setCandidateMatches(matches);
      } catch (err) {
        console.error('Failed to search case link matches:', err);
      } finally {
        setIsSearchingMatches(false);
      }
    }, 600);

    return () => clearTimeout(timer);
  }, [category, locationText, ward]);

  if (!isOpen) return null;

  const handleExtractText = async () => {
    if (!rawInputText.trim()) return;
    setIsExtracting(true);
    setExtractError(null);
    try {
      const res = await api.extractFromText(rawInputText);
      setExtractionResult(res);
      const data = res.data;

      if (data.complaint_number && data.source) {
        setTitle(`${data.source}: ${data.complaint_number} - ${data.category || 'Issue'}`);
      } else if (data.category) {
        setTitle(`Civic Grievance: ${data.category} in ${data.location_text || 'Bengaluru'}`);
      }

      if (data.category && ['GARBAGE', 'DRAINAGE', 'OTHER'].includes(data.category)) {
        setCategory(data.category as any);
      }
      if (data.location_text) {
        setLocationText(data.location_text);
      }
      setComplaintText(rawInputText);
      setActiveTab('MANUAL');
    } catch (err: any) {
      setExtractError(err.message || 'AI extraction failed');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleQuickFillSample = (sampleType: 'BBMP_GARBAGE' | 'BWSSB_DRAIN') => {
    if (sampleType === 'BBMP_GARBAGE') {
      setRawInputText(
        `BBMP Sahaaya 2.0 Grievance Receipt\nTicket ID: BBMP-2026-8819\nCategory: Garbage Blackspot Dumping\nLocation: Opposite Toit pub, 100 Feet Road, Indiranagar, Ward 112 Domlur\nFiled On: 2026-03-01 11:20 AM\nStatus: SUBMITTED\nRemarks: Huge pile of mixed commercial waste blocking sidewalk for 3 days.`
      );
    } else {
      setRawInputText(
        `BWSSB Sahayaa Portal Acknowledgement\nComplaint Ref: BWSSB-SWD-9014\nCategory: Blocked Stormwater Drain Overflow\nAddress: 80 Feet Road, near Sony World Signal, 5th Block Koramangala, Ward 151\nReported: 2026-03-03 09:15 AM\nStatus: ASSIGNED\nNote: Overflowing blackwater flooding the main carriageway.`
      );
    }
  };

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
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '20px',
      }}
    >
      <div
        className="glass-card"
        style={{
          maxWidth: '680px',
          width: '100%',
          padding: '28px',
          maxHeight: '92vh',
          overflowY: 'auto',
          border: '1px solid rgba(56, 189, 248, 0.25)',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>Report Civic Problem</h2>
              <span
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: '4px',
                  background: 'rgba(56, 189, 248, 0.15)',
                  color: '#38bdf8',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                }}
              >
                Feature 1: AI Continuity
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Open-weight AI extracts receipt data & matches cross-portal cases (BBMP Sahaaya, Swachhata, BWSSB).
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

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
          <button
            type="button"
            onClick={() => setActiveTab('SMART_EXTRACT')}
            style={{
              background: activeTab === 'SMART_EXTRACT' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
              color: activeTab === 'SMART_EXTRACT' ? '#38bdf8' : 'var(--text-muted)',
              border: activeTab === 'SMART_EXTRACT' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            ⚡ Paste Complaint Receipt / Screenshot
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('MANUAL')}
            style={{
              background: activeTab === 'MANUAL' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
              color: activeTab === 'MANUAL' ? '#38bdf8' : 'var(--text-muted)',
              border: activeTab === 'MANUAL' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            ✍ Case Details Form
          </button>
        </div>

        {/* Tab 1: Smart Extraction */}
        {activeTab === 'SMART_EXTRACT' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)' }}>
                Paste Complaint Ticket / SMS / Receipt Text
              </label>
              <div style={{ display: 'flex', gap: '6px' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', alignSelf: 'center' }}>Quick sample:</span>
                <button
                  type="button"
                  onClick={() => handleQuickFillSample('BBMP_GARBAGE')}
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: 'rgba(15, 23, 42, 0.8)',
                    color: '#38bdf8',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                  }}
                >
                  BBMP Garbage
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickFillSample('BWSSB_DRAIN')}
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: 'rgba(15, 23, 42, 0.8)',
                    color: '#38bdf8',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                  }}
                >
                  BWSSB Drain
                </button>
              </div>
            </div>

            <textarea
              className="input-field"
              rows={5}
              placeholder="Paste raw text from BBMP Sahaaya, Swachhata, BESCOM Namma 1912, or BWSSB..."
              value={rawInputText}
              onChange={(e) => setRawInputText(e.target.value)}
              style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}
            />

            {extractError && (
              <div style={{ color: '#fb7185', fontSize: '0.8rem', background: 'rgba(244, 63, 94, 0.1)', padding: '8px', borderRadius: '6px' }}>
                {extractError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                Powered by Open-Weight Model (DeepSeek V4 / Qwen 3.6 VL)
              </span>
              <button
                type="button"
                className="btn-primary"
                disabled={isExtracting || !rawInputText.trim()}
                onClick={handleExtractText}
              >
                {isExtracting ? '🤖 Extracting with Open-Weight LLM...' : '⚡ Extract Structured Data'}
              </button>
            </div>
          </div>
        )}

        {/* Extraction Feedback Banner */}
        {extractionResult && (
          <div
            style={{
              background: extractionResult.needs_review ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)',
              border: `1px solid ${extractionResult.needs_review ? 'rgba(245, 158, 11, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
              borderRadius: '8px',
              padding: '12px 16px',
              marginBottom: '18px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 600, fontSize: '0.82rem', color: extractionResult.needs_review ? '#fbbf24' : '#34d399' }}>
                {extractionResult.needs_review
                  ? '⚠️ Extracted with low-confidence fields — please review highlighted values below'
                  : '✅ Successfully extracted with high confidence'}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Confidence: {Math.round(extractionResult.data.confidence * 100)}%
              </span>
            </div>
            {extractionResult.low_confidence_fields.length > 0 && (
              <div style={{ fontSize: '0.75rem', color: '#fbbf24', marginTop: '4px' }}>
                Please check: {extractionResult.low_confidence_fields.join(', ')}
              </div>
            )}
          </div>
        )}

        {/* Candidate Cross-Portal Matches (Feature 1) */}
        {isSearchingMatches && (
          <div style={{ fontSize: '0.75rem', color: '#38bdf8', padding: '6px 0' }}>
            🔍 Evaluating cross-portal case continuity with open-weight embeddings...
          </div>
        )}
        {candidateMatches.length > 0 && (
          <div
            style={{
              background: 'rgba(56, 189, 248, 0.08)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '8px',
              padding: '14px',
              marginBottom: '20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '1rem' }}>🔗</span>
              <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#38bdf8' }}>
                Cross-Portal Case Continuity: {candidateMatches.length} Candidate Match Found
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
              Our open-weight AI engine identified an existing persistent case that appears identical or co-located:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {candidateMatches.map((match) => (
                <div
                  key={match.case_id}
                  style={{
                    background: 'rgba(15, 23, 42, 0.8)',
                    borderRadius: '6px',
                    padding: '10px 12px',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.82rem', color: '#fff' }}>
                      Case #{match.case_id}: {match.case_title}
                    </span>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: match.confidence_level === 'AUTO_LINK' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(56, 189, 248, 0.2)',
                        color: match.confidence_level === 'AUTO_LINK' ? '#34d399' : '#38bdf8',
                      }}
                    >
                      {Math.round(match.composite_score * 100)}% Match ({match.confidence_level})
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {match.explanation}
                  </div>
                  {onLinkToExistingCase && (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
                      <button
                        type="button"
                        onClick={() => {
                          onLinkToExistingCase(match.case_id, match.explanation);
                          onClose();
                        }}
                        style={{
                          background: 'rgba(56, 189, 248, 0.2)',
                          color: '#38bdf8',
                          border: '1px solid rgba(56, 189, 248, 0.4)',
                          borderRadius: '4px',
                          padding: '4px 10px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        🔗 Link to Case #{match.case_id} Instead
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 2 / Main Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {error && (
            <div
              style={{
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid rgba(244, 63, 94, 0.3)',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#fb7185',
                fontSize: '0.82rem',
              }}
            >
              {error}
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '6px' }}>
              Case Title / Summary *
            </label>
            <input
              type="text"
              required
              className="input-field"
              placeholder="e.g., Recurring Garbage Blackspot on 100ft Road Indiranagar"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '6px' }}>
                Problem Category *
              </label>
              <select
                className="input-field"
                value={category}
                onChange={(e) => setCategory(e.target.value as any)}
              >
                <option value="GARBAGE">Garbage Accumulation</option>
                <option value="DRAINAGE">Blocked Stormwater Drainage</option>
                <option value="OTHER">Other Civic Issue</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '6px' }}>
                BBMP Ward / Area *
              </label>
              <select
                className="input-field"
                value={ward}
                onChange={(e) => setWard(e.target.value)}
              >
                <option value="Ward 112 - Domlur / Indiranagar">Ward 112 - Domlur / Indiranagar</option>
                <option value="Ward 150 - Bellandur">Ward 150 - Bellandur</option>
                <option value="Ward 151 - Koramangala">Ward 151 - Koramangala</option>
                <option value="Ward 174 - HSR Layout">Ward 174 - HSR Layout</option>
                <option value="Ward 84 - Hagadur / Whitefield">Ward 84 - Hagadur / Whitefield</option>
                <option value="Ward 45 - Malleshwaram">Ward 45 - Malleshwaram</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '6px' }}>
                Physical Location / Landmark *
              </label>
              <input
                type="text"
                required
                className="input-field"
                placeholder="e.g., Opposite Toit pub, 100 Feet Road, Indiranagar"
                value={locationText}
                onChange={(e) => setLocationText(e.target.value)}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '6px' }}>
                Zonal Jurisdiction *
              </label>
              <input
                type="text"
                required
                className="input-field"
                placeholder="e.g., BBMP East Zone"
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={submitting || !title || !locationText}
            >
              {submitting ? 'Lodging Case...' : 'Create Persistent Case'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
};
