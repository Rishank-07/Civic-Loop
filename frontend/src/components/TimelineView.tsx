import React, { useState } from 'react';
import { TimelineEvent, TimelineOrigin } from '../types';

interface TimelineViewProps {
  events: TimelineEvent[];
  selectedOrigin: TimelineOrigin | 'ALL';
  onFilterOrigin: (origin: TimelineOrigin | 'ALL') => void;
}

export const TimelineView: React.FC<TimelineViewProps> = ({
  events,
  selectedOrigin,
  onFilterOrigin,
}) => {
  const [expandedEventId, setExpandedEventId] = useState<number | null>(null);

  const origins: Array<{ label: string; value: TimelineOrigin | 'ALL'; color: string }> = [
    { label: 'All Records', value: 'ALL', color: 'var(--text-main)' },
    { label: 'Source Fact', value: 'SOURCE_FACT', color: '#38bdf8' },
    { label: 'User Claim', value: 'USER_CLAIM', color: '#c084fc' },
    { label: 'AI Reco', value: 'AI_RECOMMENDATION', color: '#34d399' },
    { label: 'System Event', value: 'SYSTEM_EVENT', color: '#fbbf24' },
  ];

  return (
    <div style={{ marginTop: '16px' }}>
      {/* Header and origin filter tabs */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '12px',
        marginBottom: '16px',
        borderBottom: '1px solid var(--border-subtle)',
        paddingBottom: '12px',
      }}>
        <div>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
            Auditable Timeline (Append-Only)
          </h4>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Immutable event stream with cryptographic and database trigger guarantees.
          </p>
        </div>

        {/* Origin Filters */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {origins.map((orig) => (
            <button
              key={orig.value}
              onClick={() => onFilterOrigin(orig.value)}
              style={{
                background: selectedOrigin === orig.value ? 'rgba(255, 255, 255, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                color: selectedOrigin === orig.value ? orig.color : 'var(--text-muted)',
                border: selectedOrigin === orig.value ? `1px solid ${orig.color}` : '1px solid var(--border-subtle)',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {orig.label}
            </button>
          ))}
        </div>
      </div>

      {/* Events List */}
      {events.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '36px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
          No timeline events match the selected filter.
        </div>
      ) : (
        <div style={{ position: 'relative', paddingLeft: '20px' }}>
          {/* Vertical Timeline bar */}
          <div style={{
            position: 'absolute',
            left: '7px',
            top: '8px',
            bottom: '8px',
            width: '2px',
            background: 'linear-gradient(to bottom, #38bdf8, #818cf8, #a855f7)',
            opacity: 0.3,
          }} />

          {events.map((evt) => {
            const isExpanded = expandedEventId === evt.id;
            return (
              <div
                key={evt.id}
                style={{
                  position: 'relative',
                  marginBottom: '16px',
                  paddingLeft: '16px',
                }}
              >
                {/* Node icon */}
                <div style={{
                  position: 'absolute',
                  left: '-17px',
                  top: '4px',
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background:
                    evt.origin === 'SOURCE_FACT' ? '#38bdf8' :
                    evt.origin === 'USER_CLAIM' ? '#c084fc' :
                    evt.origin === 'AI_RECOMMENDATION' ? '#34d399' : '#fbbf24',
                  boxShadow: '0 0 8px currentColor',
                }} />

                <div className="glass-card" style={{ padding: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span className={`origin-badge ${evt.origin}`}>
                        {evt.origin}
                      </span>
                      <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f1f5f9' }}>
                        {evt.event_type}
                      </span>
                    </div>

                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                      {new Date(evt.created_at).toLocaleString()}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '16px', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    <span>
                      <strong style={{ color: 'var(--text-dim)' }}>Actor:</strong> {evt.actor}
                    </span>
                    <span>
                      <strong style={{ color: 'var(--text-dim)' }}>Source:</strong> {evt.source}
                    </span>
                  </div>

                  {/* Payload preview / inspector */}
                  {evt.payload_json && Object.keys(evt.payload_json).length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <button
                        onClick={() => setExpandedEventId(isExpanded ? null : evt.id)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--accent-cyan)',
                          fontSize: '0.72rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: 0,
                        }}
                      >
                        {isExpanded ? '▼ Hide Payload Data' : '▶ Inspect Event Payload'}
                      </button>

                      {isExpanded && (
                        <pre style={{
                          marginTop: '8px',
                          background: 'rgba(0, 0, 0, 0.4)',
                          padding: '10px',
                          borderRadius: '8px',
                          fontSize: '0.72rem',
                          color: '#a5f3fc',
                          overflowX: 'auto',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                        }}>
                          {JSON.stringify(evt.payload_json, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
