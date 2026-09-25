import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import { useAuth } from '../context/AuthContext';
import { userAPI } from '../api/api';

const GENRES = [
  'Action', 'Adventure', 'Animation', 'Comedy', 'Crime', 'Documentary',
  'Drama', 'Family', 'Fantasy', 'History', 'Horror', 'Music', 'Mystery',
  'Romance', 'Science Fiction', 'Thriller', 'War', 'Western',
];

const FREQ_LABELS = { daily: 'Every day', weekly: 'A few times a week', monthly: 'A few times a month' };

function useSubmit(fn) {
  const [loading, setLoading] = useState(false);
  const [msg,     setMsg]     = useState('');
  const [err,     setErr]     = useState('');
  const submit = async (...args) => {
    setLoading(true); setMsg(''); setErr('');
    try { await fn(...args); setMsg('Saved!'); setTimeout(() => setMsg(''), 3000); }
    catch (e) { setErr(e.response?.data?.error || 'Error saving. Try again.'); }
    finally { setLoading(false); }
  };
  return { loading, msg, err, submit };
}

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();

  const [name, setName] = useState({
    firstName: user?.firstName ?? '',
    lastName:  user?.lastName  ?? '',
  });
  const profileSave = useSubmit(async () => {
    await userAPI.updateProfile({ firstName: name.firstName, lastName: name.lastName });
    await refreshUser();
  });

  const [genres, setGenres] = useState(user?.favoriteGenres ?? []);
  const toggleGenre = g => setGenres(prev => prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]);
  const genreSave = useSubmit(async () => {
    await userAPI.updateProfile({ favoriteGenres: genres });
    await refreshUser();
  });

  const [prefs, setPrefs] = useState({
    includeWatched:    user?.preferences?.includeWatched    ?? false,
    watchingFrequency: user?.preferences?.watchingFrequency ?? 'weekly',
  });
  const prefsSave = useSubmit(async () => {
    await userAPI.updateProfile({ preferences: prefs });
    await refreshUser();
  });

  const [passwords, setPasswords] = useState({ current: '', newPass: '', confirm: '' });
  const pwSave = useSubmit(async () => {
    if (passwords.newPass !== passwords.confirm) throw new Error('Passwords do not match');
    await userAPI.changePassword({ currentPassword: passwords.current, newPassword: passwords.newPass });
    setPasswords({ current: '', newPass: '', confirm: '' });
  });

  const initials = user
    ? `${user.firstName?.[0] ?? ''}${user.lastName?.[0] ?? ''}`.toUpperCase()
    : '?';

  return (
    <div className="page-enter">
      <Navbar />
      <div className="profile">
        {/* Header */}
        <div className="profile-header">
          <div className="profile-avatar-lg">{initials}</div>
          <div className="profile-name">{user?.firstName} {user?.lastName}</div>
          <div className="profile-email">{user?.email}</div>
          <div className="profile-stats">
            <div className="stat-card">
              <div className="stat-value">{user?.watchedMovies?.length ?? 0}</div>
              <div className="stat-label">Watched</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{user?.favoriteMovies?.length ?? 0}</div>
              <div className="stat-label">Favourites</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{user?.favoriteGenres?.length ?? 0}</div>
              <div className="stat-label">Genres</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ fontSize: 18 }}>{FREQ_LABELS[user?.preferences?.watchingFrequency] ?? '—'}</div>
              <div className="stat-label">Viewing freq.</div>
            </div>
          </div>
        </div>

        {/* Name */}
        <div className="profile-section">
          <div className="profile-section-title">Account Info</div>
          <div className="profile-form">
            <div className="profile-row">
              <div className="field">
                <label>First name</label>
                <input className="input" value={name.firstName}
                  onChange={e => setName(n => ({ ...n, firstName: e.target.value }))} />
              </div>
              <div className="field">
                <label>Last name</label>
                <input className="input" value={name.lastName}
                  onChange={e => setName(n => ({ ...n, lastName: e.target.value }))} />
              </div>
            </div>
            {profileSave.err && <div className="error-banner">{profileSave.err}</div>}
            <div className="profile-action">
              {profileSave.msg && <span className="success-msg">✓ {profileSave.msg}</span>}
              <button className="btn btn-primary btn-sm" onClick={profileSave.submit} disabled={profileSave.loading}>
                {profileSave.loading ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>

        {/* Genres */}
        <div className="profile-section">
          <div className="profile-section-title">Favourite Genres</div>
          <div className="genre-grid" style={{ marginBottom: 16 }}>
            {GENRES.map(g => (
              <button key={g} type="button"
                className={`genre-chip ${genres.includes(g) ? 'selected' : ''}`}
                onClick={() => toggleGenre(g)}
              >{g}</button>
            ))}
          </div>
          {genreSave.err && <div className="error-banner">{genreSave.err}</div>}
          <div className="profile-action">
            {genreSave.msg && <span className="success-msg">✓ {genreSave.msg}</span>}
            <button className="btn btn-primary btn-sm" onClick={genreSave.submit} disabled={genreSave.loading}>
              {genreSave.loading ? 'Saving…' : 'Save Genres'}
            </button>
          </div>
        </div>

        {/* Preferences */}
        <div className="profile-section">
          <div className="profile-section-title">Preferences</div>
          <div className="profile-form">
            <div className="field">
              <label>Watching frequency</label>
              <select className="input" value={prefs.watchingFrequency}
                onChange={e => setPrefs(p => ({ ...p, watchingFrequency: e.target.value }))}>
                <option value="daily">Every day</option>
                <option value="weekly">A few times a week</option>
                <option value="monthly">A few times a month</option>
              </select>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer', padding: '12px 16px', background: 'var(--bg-3)', borderRadius: 'var(--r)', border: '1.5px solid var(--border)' }}>
              <input type="checkbox" checked={prefs.includeWatched}
                onChange={e => setPrefs(p => ({ ...p, includeWatched: e.target.checked }))} />
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Include already-watched films</div>
                <div style={{ fontSize: 12, color: 'var(--text-2)' }}>Re-recommend movies you have seen before</div>
              </div>
            </label>
            {prefsSave.err && <div className="error-banner">{prefsSave.err}</div>}
            <div className="profile-action">
              {prefsSave.msg && <span className="success-msg">✓ {prefsSave.msg}</span>}
              <button className="btn btn-primary btn-sm" onClick={prefsSave.submit} disabled={prefsSave.loading}>
                {prefsSave.loading ? 'Saving…' : 'Save Preferences'}
              </button>
            </div>
          </div>
        </div>

        {/* Change password */}
        <div className="profile-section">
          <div className="profile-section-title">Change Password</div>
          <div className="profile-form">
            <div className="field">
              <label>Current password</label>
              <input type="password" className="input" placeholder="••••••••"
                value={passwords.current}
                onChange={e => setPasswords(p => ({ ...p, current: e.target.value }))} />
            </div>
            <div className="profile-row">
              <div className="field">
                <label>New password</label>
                <input type="password" className="input" placeholder="Min. 8 characters"
                  value={passwords.newPass}
                  onChange={e => setPasswords(p => ({ ...p, newPass: e.target.value }))} />
              </div>
              <div className="field">
                <label>Confirm new</label>
                <input type="password" className="input" placeholder="Repeat password"
                  value={passwords.confirm}
                  onChange={e => setPasswords(p => ({ ...p, confirm: e.target.value }))} />
              </div>
            </div>
            {pwSave.err && <div className="error-banner">{pwSave.err}</div>}
            <div className="profile-action">
              {pwSave.msg && <span className="success-msg">✓ Password updated</span>}
              <button className="btn btn-primary btn-sm" onClick={pwSave.submit} disabled={pwSave.loading}>
                {pwSave.loading ? 'Updating…' : 'Update Password'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
