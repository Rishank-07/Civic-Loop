import React from 'react';

interface NavbarProps {
  currentUser: { email: string; name: string; role: string };
  onSwitchUser: (role: 'CITIZEN' | 'OFFICER' | 'ADMIN') => void;
  onOpenNewCase: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentUser,
  onSwitchUser,
  onOpenNewCase,
}) => {
  return (
    <header style={{
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(9, 13, 22, 0.85)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '14px 28px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 16px rgba(56, 189, 248, 0.4)',
        }}>
          <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#fff' }}>⟳</span>
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ fontSize: '1.25rem', fontWeight: '800', letterSpacing: '-0.02em', color: '#fff' }}>
              Civic<span style={{ color: 'var(--accent-cyan)' }}>Loop</span>
            </h1>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '2px 7px',
              borderRadius: '4px',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#34d399',
              border: '1px solid rgba(16, 185, 129, 0.3)',
            }}>
              OPEN-WEIGHT AGENT
            </span>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 600,
              padding: '2px 7px',
              borderRadius: '4px',
              background: 'rgba(56, 189, 248, 0.1)',
              color: '#38bdf8',
            }}>
              Bengaluru (BBMP/GBA)
            </span>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Persistent Civic Problem Management · Garbage & SWD Drainage
          </p>
        </div>
      </div>

      {/* Actions & Role Switcher */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Switch Persona */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          background: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '8px',
          padding: '4px',
          gap: '4px',
        }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', padding: '0 6px', fontWeight: 600 }}>
            ROLE:
          </span>
          <button
            onClick={() => onSwitchUser('CITIZEN')}
            style={{
              background: currentUser.role === 'CITIZEN' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
              color: currentUser.role === 'CITIZEN' ? '#38bdf8' : 'var(--text-muted)',
              border: 'none',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Citizen
          </button>
          <button
            onClick={() => onSwitchUser('OFFICER')}
            style={{
              background: currentUser.role === 'OFFICER' ? 'rgba(245, 158, 11, 0.2)' : 'transparent',
              color: currentUser.role === 'OFFICER' ? '#fbbf24' : 'var(--text-muted)',
              border: 'none',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            BBMP Officer
          </button>
          <button
            onClick={() => onSwitchUser('ADMIN')}
            style={{
              background: currentUser.role === 'ADMIN' ? 'rgba(168, 85, 247, 0.2)' : 'transparent',
              color: currentUser.role === 'ADMIN' ? '#c084fc' : 'var(--text-muted)',
              border: 'none',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Admin
          </button>
        </div>

        {/* Current User Info */}
        <div style={{ textAlign: 'right', display: 'none', minWidth: '120px' }}>
          <div style={{ fontSize: '0.82rem', fontWeight: 600 }}>{currentUser.name}</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>{currentUser.email}</div>
        </div>

        {/* New Case Button */}
        <button className="btn-primary" onClick={onOpenNewCase}>
          <span style={{ fontSize: '1rem', lineHeight: '1' }}>+</span>
          <span>Report Civic Issue</span>
        </button>
      </div>
    </header>
  );
};
