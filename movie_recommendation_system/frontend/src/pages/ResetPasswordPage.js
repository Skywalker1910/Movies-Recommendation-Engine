import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authAPI } from '../api/api';

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [complete, setComplete] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async event => {
    event.preventDefault();
    setError('');
    if (!token) return setError('This reset link does not contain a token.');
    if (password.length < 8) return setError('Password must contain at least 8 characters.');
    if (password !== confirm) return setError('Passwords do not match.');
    setLoading(true);
    try {
      await authAPI.resetPassword({ token, newPassword: password });
      setComplete(true);
    } catch (err) {
      setError(err.response?.data?.error || 'Password reset failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-bg page-enter">
      <div className="auth-card">
        <div className="auth-logo">CineMatch</div>
        <h1 className="auth-title">Reset password</h1>
        {complete ? (
          <>
            <p className="auth-sub">Your password has been updated.</p>
            <Link to="/login" className="btn btn-primary">Continue to sign in</Link>
          </>
        ) : (
          <form className="auth-form" onSubmit={submit}>
            <p className="auth-sub">Choose a new password for your account.</p>
            {error && <div className="auth-error">{error}</div>}
            <div className="field">
              <label htmlFor="reset-password">New password</label>
              <input id="reset-password" type="password" className="input" value={password}
                onChange={event => setPassword(event.target.value)} autoComplete="new-password" />
            </div>
            <div className="field">
              <label htmlFor="reset-confirm">Confirm password</label>
              <input id="reset-confirm" type="password" className="input" value={confirm}
                onChange={event => setConfirm(event.target.value)} autoComplete="new-password" />
            </div>
            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? 'Resetting...' : 'Reset password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
