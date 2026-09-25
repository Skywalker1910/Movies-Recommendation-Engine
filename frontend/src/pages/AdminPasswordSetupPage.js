import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { adminAPI } from '../api/api';

export default function AdminPasswordSetupPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [complete, setComplete] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async event => {
    event.preventDefault();
    setError('');
    if (!token) return setError('This setup link does not contain a token.');
    if (password.length < 12) return setError('Use at least 12 characters.');
    if (password !== confirmation) return setError('Passwords do not match.');
    setBusy(true);
    try {
      await adminAPI.setPassword({ token, newPassword: password });
      sessionStorage.removeItem('adminToken');
      setComplete(true);
    } catch (err) {
      setError(err.response?.data?.error || 'Administrator password setup failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="admin-login-page page-enter">
      <section className="admin-login-card">
        <div className="admin-login-mark">AC</div>
        <div className="admin-eyebrow">Administrator setup</div>
        <h1>{complete ? 'Password configured' : 'Set administrator password'}</h1>
        {complete ? (
          <>
            <p>Your isolated administrator credential is ready.</p>
            <Link to="/admin" className="btn btn-primary">Continue to admin login</Link>
          </>
        ) : (
          <form className="auth-form" onSubmit={submit}>
            {error && <div className="error-banner">{error}</div>}
            <label className="field">New password
              <input className="input" type="password" autoComplete="new-password"
                value={password} onChange={event => setPassword(event.target.value)} />
            </label>
            <label className="field">Confirm password
              <input className="input" type="password" autoComplete="new-password"
                value={confirmation} onChange={event => setConfirmation(event.target.value)} />
            </label>
            <button className="btn btn-primary" disabled={busy}>
              {busy ? 'Saving...' : 'Set administrator password'}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
