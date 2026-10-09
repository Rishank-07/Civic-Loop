import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { CaseCard } from './components/CaseCard';
import { TimelineView } from './components/TimelineView';
import { NewCaseModal } from './components/NewCaseModal';
import { api } from './api/client';
import { Case, TimelineEvent, TimelineOrigin, VerificationState } from './types';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState({
    email: 'citizen@civicloop.org',
    name: 'Ramesh Kumar',
    role: 'CITIZEN',
  });

  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [selectedCaseDetail, setSelectedCaseDetail] = useState<Case | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [timelineOriginFilter, setTimelineOriginFilter] = useState<TimelineOrigin | 'ALL'>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  const [isNewCaseOpen, setIsNewCaseOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [disputeModalOpen, setDisputeModalOpen] = useState(false);
  const [disputeReason, setDisputeReason] = useState('');
  const [aiHealth, setAiHealth] = useState<{
    status?: string;
    agent_model?: string;
    vision_model?: string;
    embed_model?: string;
  }>({
    status: 'healthy',
    agent_model: 'DeepSeek V4',
    vision_model: 'Qwen 3.6 VL',
    embed_model: 'BGE-M3',
  });

  // Initial load and authentication
  useEffect(() => {
    switchUser('CITIZEN');
    api.getAIHealth().then((h) => setAiHealth(h)).catch(() => {});
  }, []);


  const switchUser = async (role: 'CITIZEN' | 'OFFICER' | 'ADMIN') => {
    setLoading(true);
    let email = 'citizen@civicloop.org';
    if (role === 'OFFICER') email = 'officer@bbmp.gov.in';
    if (role === 'ADMIN') email = 'admin@civicloop.org';

    try {
      const loginData = await api.login(email, 'Password123!');
      setCurrentUser({
        email: loginData.email,
        name: loginData.name,
        role: loginData.role,
      });
      await loadCases();
    } catch (err) {
      console.error('Failed to switch user:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadCases = async () => {
    try {
      const data = await api.getCases();
      setCases(data);
      if (data.length > 0 && !selectedCaseId) {
        setSelectedCaseId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load cases:', err);
    }
  };

  // Load detailed case and timeline when selected
  useEffect(() => {
    if (!selectedCaseId) return;

    const fetchDetails = async () => {
      try {
        const detail = await api.getCase(selectedCaseId);
        setSelectedCaseDetail(detail);

        const filter = timelineOriginFilter === 'ALL' ? undefined : timelineOriginFilter;
        const events = await api.getTimeline(selectedCaseId, filter);
        setTimelineEvents(events);
      } catch (err) {
        console.error('Failed to load case detail:', err);
      }
    };

    fetchDetails();
  }, [selectedCaseId, timelineOriginFilter]);

  const handleCreateCase = async (data: any) => {
    await api.createCase(data);
    await loadCases();
  };

  const handleVerificationTransition = async (targetState: VerificationState, reason: string) => {
    if (!selectedCaseId) return;
    setTransitioning(true);
    try {
      await api.transitionVerification(selectedCaseId, targetState, reason);
      // Refresh case details and timeline
      const detail = await api.getCase(selectedCaseId);
      setSelectedCaseDetail(detail);
      const events = await api.getTimeline(selectedCaseId);
      setTimelineEvents(events);
      await loadCases();
      setDisputeModalOpen(false);
      setDisputeReason('');
    } catch (err: any) {
      alert(`Transition error: ${err.message}`);
    } finally {
      setTransitioning(false);
    }
  };

  // Filter cases
  const filteredCases = cases.filter((c) => {
    if (statusFilter !== 'ALL' && c.status !== statusFilter) return false;
    if (categoryFilter !== 'ALL' && c.issue_category !== categoryFilter) return false;
    return true;
  });

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        currentUser={currentUser}
        onSwitchUser={switchUser}
        onOpenNewCase={() => setIsNewCaseOpen(true)}
      />

      {loading && (
        <div style={{
          background: 'rgba(56, 189, 248, 0.1)',
          color: 'var(--accent-cyan)',
          padding: '4px 16px',
          fontSize: '0.75rem',
          textAlign: 'center',
          borderBottom: '1px solid rgba(56, 189, 248, 0.2)',
        }}>
          Synchronizing cases and timeline...
        </div>
      )}

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '24px 28px', maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
        {/* KPI Summary Banner */}
        <section style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '24px',
        }}>
          <div className="glass-card" style={{ padding: '16px 20px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>TOTAL CIVIC CASES</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#f8fafc', marginTop: '4px' }}>
              {cases.length}
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)' }}>GBA / BBMP Jurisdiction</span>
          </div>

          <div className="glass-card" style={{ padding: '16px 20px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>MONITORING & OPEN</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#38bdf8', marginTop: '4px' }}>
              {cases.filter(c => c.status !== 'CLOSED').length}
            </div>
            <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Persistent Follow-up</span>
          </div>

          <div className="glass-card" style={{ padding: '16px 20px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>DISPUTED CLOSURES</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fb7185', marginTop: '4px' }}>
              {cases.filter(c => c.verification_state === 'RESOLUTION_DISPUTED').length}
            </div>
            <span style={{ fontSize: '0.72rem', color: '#fb7185' }}>Physical Audit Refutes Portal</span>
          </div>

          <div className="glass-card" style={{ padding: '16px 20px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600 }}>CITIZEN CONFIRMED</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#34d399', marginTop: '4px' }}>
              {cases.filter(c => c.verification_state === 'CITIZEN_CONFIRMED_RESOLVED').length}
            </div>
            <span style={{ fontSize: '0.72rem', color: '#34d399' }}>Verified Resolved</span>
          </div>
        </section>

        {/* Master-Detail Split Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '24px', alignItems: 'start' }}>
          {/* Left Column: Cases List */}
          <div>
            {/* Filter toolbar */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '14px', flexWrap: 'wrap' }}>
              <select
                className="input-field"
                style={{ width: 'auto', flex: 1, padding: '6px 10px', fontSize: '0.8rem' }}
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                <option value="ALL">All Categories</option>
                <option value="GARBAGE">Garbage</option>
                <option value="DRAINAGE">Drainage / SWD</option>
              </select>

              <select
                className="input-field"
                style={{ width: 'auto', flex: 1, padding: '6px 10px', fontSize: '0.8rem' }}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="ALL">All Statuses</option>
                <option value="OPEN">Open</option>
                <option value="MONITORING">Monitoring</option>
                <option value="CLOSED">Closed</option>
              </select>
            </div>

            {/* List */}
            <div>
              {filteredCases.map((c) => (
                <CaseCard
                  key={c.id}
                  caseItem={c}
                  isSelected={c.id === selectedCaseId}
                  onSelect={() => setSelectedCaseId(c.id)}
                />
              ))}

              {filteredCases.length === 0 && (
                <div className="glass-card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No cases found.
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Case Deep Dive & Timeline */}
          {selectedCaseDetail ? (
            <div className="glass-card" style={{ padding: '28px' }}>
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', background: 'rgba(255, 255, 255, 0.08)', color: '#38bdf8' }}>
                      {selectedCaseDetail.issue_category}
                    </span>
                    <span className={`status-pill ${selectedCaseDetail.status}`}>
                      ● {selectedCaseDetail.status}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      ID #{selectedCaseDetail.id}
                    </span>
                  </div>

                  <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#fff', marginBottom: '6px' }}>
                    {selectedCaseDetail.title}
                  </h2>
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                    📍 {selectedCaseDetail.location_text}
                  </p>
                </div>

                {/* Verification State Callout */}
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', display: 'block', marginBottom: '4px' }}>
                    Independent CivicLoop Verification
                  </span>
                  <div className={`verification-badge ${selectedCaseDetail.verification_state}`} style={{ fontSize: '0.85rem', padding: '6px 14px' }}>
                    {selectedCaseDetail.verification_state}
                  </div>
                </div>
              </div>

              {/* Action Bar for Verification State Machine (Deterministic Transitions) */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '24px',
              }}>
                <div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f8fafc' }}>
                    Citizen Ground Truth Actions
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                    State machine rejects illegal jumps. Records auditable timeline event.
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  {selectedCaseDetail.verification_state !== 'CITIZEN_CONFIRMED_RESOLVED' && (
                    <button
                      className="btn-secondary"
                      style={{ color: '#34d399', borderColor: 'rgba(16, 185, 129, 0.3)' }}
                      disabled={transitioning}
                      onClick={() => handleVerificationTransition(
                        'CITIZEN_CONFIRMED_RESOLVED',
                        'Citizen verified on-site that problem is completely resolved.'
                      )}
                    >
                      ✓ Confirm Resolved
                    </button>
                  )}

                  {selectedCaseDetail.verification_state !== 'RESOLUTION_DISPUTED' && (
                    <button
                      className="btn-secondary"
                      style={{ color: '#fb7185', borderColor: 'rgba(244, 63, 94, 0.3)' }}
                      disabled={transitioning}
                      onClick={() => setDisputeModalOpen(true)}
                    >
                      ⚠ Dispute Resolution
                    </button>
                  )}

                  {selectedCaseDetail.verification_state !== 'INSUFFICIENT_EVIDENCE' && (
                    <button
                      className="btn-secondary"
                      disabled={transitioning}
                      onClick={() => handleVerificationTransition(
                        'INSUFFICIENT_EVIDENCE',
                        'Evidence lacks clear landmark geolocation or visual clarity.'
                      )}
                    >
                      ❓ Request Evidence
                    </button>
                  )}
                </div>
              </div>

              {/* Official Complaint Records (Honesty Rule 6: Separate from Verification State) */}
              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', marginBottom: '10px' }}>
                  Official Complaint Records (Immutable)
                </h4>
                {selectedCaseDetail.complaint_records && selectedCaseDetail.complaint_records.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {selectedCaseDetail.complaint_records.map((rec) => (
                      <div
                        key={rec.id}
                        style={{
                          background: 'rgba(0, 0, 0, 0.25)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '10px',
                          padding: '12px 16px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#38bdf8' }}>
                              {rec.source}
                            </span>
                            {rec.retrieval_method === 'MOCK' && (
                              <span style={{
                                fontSize: '0.65rem',
                                fontWeight: 700,
                                background: 'rgba(245, 158, 11, 0.2)',
                                color: '#fbbf24',
                                padding: '1px 6px',
                                borderRadius: '4px',
                                border: '1px solid rgba(245, 158, 11, 0.3)',
                              }}>
                                SIMULATED MOCK CONNECTOR
                              </span>
                            )}
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                              Ref: {rec.external_id || 'N/A'}
                            </span>
                          </div>

                          <span style={{
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '4px',
                            background: 'rgba(255, 255, 255, 0.08)',
                            color: '#e2e8f0',
                          }}>
                            Official Portal Status: {rec.official_status}
                          </span>
                        </div>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                          "{rec.raw_text}"
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                    No external complaints recorded yet.
                  </div>
                )}
              </div>

              {/* Auditable Timeline View (Append-Only) */}
              <TimelineView
                events={timelineEvents}
                selectedOrigin={timelineOriginFilter}
                onFilterOrigin={setTimelineOriginFilter}
              />
            </div>
          ) : (
            <div className="glass-card" style={{ padding: '48px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Select a case from the left list to view details and timeline.
            </div>
          )}
        </div>
      </main>

      {/* New Case Modal */}
      <NewCaseModal
        isOpen={isNewCaseOpen}
        onClose={() => setIsNewCaseOpen(false)}
        onSubmit={handleCreateCase}
      />

      {/* Dispute Reason Modal */}
      {disputeModalOpen && (
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
          <div className="glass-card" style={{ maxWidth: '480px', width: '100%', padding: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '8px' }}>
              Dispute Official Resolution
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
              Why is the authority's resolution invalid? (This will be permanently recorded in the append-only timeline).
            </p>
            <textarea
              className="input-field"
              rows={3}
              placeholder="e.g. Visited the site this morning. The contractor only swept the surface; the SWD culvert remains choked with silt and trash."
              value={disputeReason}
              onChange={(e) => setDisputeReason(e.target.value)}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '14px' }}>
              <button className="btn-secondary" onClick={() => setDisputeModalOpen(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                style={{ background: 'linear-gradient(135deg, #e11d48 0%, #be123c 100%)' }}
                disabled={!disputeReason.trim() || transitioning}
                onClick={() => handleVerificationTransition('RESOLUTION_DISPUTED', disputeReason)}
              >
                Log Official Dispute
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Open-Weight AI Model Footer */}
      <footer

        style={{
          borderTop: '1px solid var(--border-subtle)',
          background: 'rgba(9, 13, 22, 0.95)',
          padding: '16px 28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.78rem',
          color: 'var(--text-muted)',
          marginTop: 'auto',
          zIndex: 40,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span
            style={{
              display: 'inline-block',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: aiHealth.status === 'healthy' ? '#10b981' : '#f59e0b',
              boxShadow: aiHealth.status === 'healthy' ? '0 0 8px #10b981' : '0 0 8px #f59e0b',
            }}
          />
          <span>
            <strong style={{ color: 'var(--text-main)' }}>Open-Weight AI Stack:</strong>{' '}
            Agent: <span style={{ color: '#38bdf8' }}>{aiHealth.agent_model || 'DeepSeek V4'}</span> • Vision:{' '}
            <span style={{ color: '#a78bfa' }}>{aiHealth.vision_model || 'Qwen 3.6 VL'}</span> • Embeddings:{' '}
            <span style={{ color: '#34d399' }}>{aiHealth.embed_model || 'BGE-M3'}</span>
          </span>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <span>Track: PS03 Open-Source AI Agent</span>
          <span style={{ color: 'var(--text-dim)' }}>Strictly Zero Proprietary API Dependencies</span>
        </div>
      </footer>
    </div>
  );
};

