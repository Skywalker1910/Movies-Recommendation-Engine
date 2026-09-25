import React, { useEffect, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate          = useNavigate();
  const [solid, setSolid] = useState(false);
  const [menu,  setMenu]  = useState(false);

  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const initials = user
    ? `${user.firstName?.[0] ?? ''}${user.lastName?.[0] ?? ''}`.toUpperCase()
    : '?';

  return (
    <nav className={`nav ${solid ? 'solid' : ''}`}>
      <Link to="/dashboard" className="nav-logo">CineMatch</Link>

      <div className="nav-links">
        <NavLink to="/dashboard" className={({ isActive }) => `nav-link nav-link-main ${isActive ? 'active' : ''}`}>
          Home
        </NavLink>
        <NavLink to="/profile" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          Profile
        </NavLink>
      </div>

      <div className="nav-user">
        <div
          className="nav-avatar"
          onClick={() => setMenu(m => !m)}
          title={user ? `${user.firstName} ${user.lastName}` : ''}
        >
          {initials}
        </div>

        {menu && (
          <div style={{
            position: 'absolute', top: 64, right: 48, background: 'var(--bg-2)',
            border: '1px solid var(--border)', borderRadius: 'var(--r-lg)',
            padding: '8px 0', minWidth: 160, zIndex: 200,
            boxShadow: 'var(--shadow-lg)',
          }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{user?.firstName} {user?.lastName}</div>
              <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{user?.email}</div>
            </div>
            <Link to="/profile" onClick={() => setMenu(false)}
              style={{ display: 'block', padding: '10px 16px', fontSize: 14, color: 'var(--text-2)', transition: 'all .2s' }}
              onMouseEnter={e => e.target.style.background = 'var(--bg-3)'}
              onMouseLeave={e => e.target.style.background = 'transparent'}
            >
              Settings
            </Link>
            <button onClick={handleLogout} style={{
              display: 'block', width: '100%', textAlign: 'left',
              padding: '10px 16px', fontSize: 14, color: '#ff7070',
              background: 'transparent', border: 'none', cursor: 'pointer',
              transition: 'all .2s',
            }}
              onMouseEnter={e => e.target.style.background = 'var(--bg-3)'}
              onMouseLeave={e => e.target.style.background = 'transparent'}
            >
              Sign Out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
