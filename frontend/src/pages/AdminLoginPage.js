import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAdminAuth } from '../context/AdminAuthContext';

export default function AdminLoginPage() {
  const { login } = useAdminAuth();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async event => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(form.email, form.password);
    } catch (err) {
      setError(err.response?.data?.error || 'Administrator sign-in failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="admin-login-page page-enter">
      <section className="admin-login-card">
        <div className="admin-login-mark">AC</div>
        <div className="admin-eyebrow">Restricted system</div>
        <h1>Administrator access</h1>
        <p>Use the credentials assigned to your separate administrator account.</p>
        {error && <div className="error-banner">{error}</div>}
        <form className="auth-form" onSubmit={submit}>
          <label className="field">Administrator email
            <input className="input" type="email" required autoComplete="username"
              value={form.email}
              onChange={event => setForm(current => ({ ...current, email: event.target.value }))} />
          </label>
          <label className="field">Password
            <input className="input" type="password" required autoComplete="current-password"
              value={form.password}
              onChange={event => setForm(current => ({ ...current, password: event.target.value }))} />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Authenticating...' : 'Access admin center'}
          </button>
        </form>
        <Link to="/" className="admin-back-link">Return to the application</Link>
      </section>
    </main>
  );
}
