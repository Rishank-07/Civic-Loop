import React from 'react';
import { Case } from '../types';

interface CaseCardProps {
  caseItem: Case;
  isSelected: boolean;
  onSelect: () => void;
}

export const CaseCard: React.FC<CaseCardProps> = ({ caseItem, isSelected, onSelect }) => {
  const getCategoryColor = (cat: string) => {
    switch (cat) {
      case 'GARBAGE':
        return '#f59e0b';
      case 'DRAINAGE':
        return '#38bdf8';
      default:
        return '#a855f7';
    }
  };

  return (
    <div
      onClick={onSelect}
      className="glass-card"
      style={{
        padding: '20px',
        cursor: 'pointer',
        border: isSelected ? '1px solid var(--accent-cyan)' : undefined,
        background: isSelected ? 'rgba(30, 41, 59, 0.95)' : undefined,
        marginBottom: '12px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: '4px',
            background: 'rgba(255, 255, 255, 0.08)',
            color: getCategoryColor(caseItem.issue_category),
          }}>
            {caseItem.issue_category}
          </span>
          <span className={`status-pill ${caseItem.status}`}>
            ● {caseItem.status}
          </span>
        </div>

        <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
          Case #{caseItem.id}
        </span>
      </div>

      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '8px', lineHeight: 1.4 }}>
        {caseItem.title}
      </h3>

      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px', lineHeight: 1.4 }}>
        📍 {caseItem.location_text}
      </p>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
        <div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'block' }}>
            Ward & Zone
          </span>
          <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#e2e8f0' }}>
            {caseItem.ward}
          </span>
        </div>

        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', display: 'block', marginBottom: '2px' }}>
            Independent Verification
          </span>
          <span className={`verification-badge ${caseItem.verification_state}`}>
            {caseItem.verification_state === 'CITIZEN_CONFIRMED_RESOLVED' && '✓ Resolved'}
            {caseItem.verification_state === 'RESOLUTION_DISPUTED' && '⚠ Disputed Closure'}
            {caseItem.verification_state === 'AWAITING_VERIFICATION' && '⏳ Awaiting Verification'}
            {caseItem.verification_state === 'INSUFFICIENT_EVIDENCE' && '❓ Insufficient Evidence'}
          </span>
        </div>
      </div>
    </div>
  );
};
