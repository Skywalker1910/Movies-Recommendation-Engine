import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../api/api';
import { useAdminAuth } from '../context/AdminAuthContext';

const MODEL_FIELDS = [
  ['popularityWeight', 'Popularity weight', 0.05],
  ['funkSvdWeight', 'FunkSVD weight', 0.05],
  ['neuMfWeight', 'NeuMF weight', 0.05],
  ['genreBoost', 'Genre boost', 0.05],
  ['candidatePoolSize', 'Candidate pool', 1],
  ['similarUserCount', 'Similar users', 1],
  ['minimumSimilarity', 'Minimum similarity', 0.01],
];

const textList = value => (value || []).join(', ');
const parseTextList = value => value.split(',').map(item => item.trim()).filter(Boolean);
const parseIdList = value => value.split(',').map(item => item.trim()).filter(Boolean).map(item => {
  const id = Number(item);
  if (!Number.isInteger(id) || id <= 0) throw new Error('Movie IDs must be positive integers.');
  return id;
});

function userForm(user) {
  return {
    firstName: user.firstName || '',
    lastName: user.lastName || '',
    email: user.email || '',
    movielensUserId: user.movielensUserId ?? '',
    favoriteGenres: textList(user.favoriteGenres),
    favoriteMovies: textList(user.favoriteMovies),
    watchedMovies: textList(user.watchedMovies),
    includeWatched: Boolean(user.preferences?.includeWatched),
    watchingFrequency: user.preferences?.watchingFrequency || 'weekly',
    isActive: user.isActive !== false,
  };
}

export default function AdminPage() {
  const { admin, logout } = useAdminAuth();
  const [summary, setSummary] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [modelInventory, setModelInventory] = useState({ models: [], pipeline: [] });
  const [adminAccounts, setAdminAccounts] = useState([]);
  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [modelData, setModelData] = useState({ versions: [] });
  const [modelForm, setModelForm] = useState({});
  const [modelReason, setModelReason] = useState('');
  const [audit, setAudit] = useState([]);
  const [resetLink, setResetLink] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const reportError = err => setError(err.response?.data?.error || err.message || 'Request failed.');

  const loadUsers = async (search = query) => {
    const response = await adminAPI.users(search);
    setUsers(response.data.items);
    setTotalUsers(response.data.total);
  };

  const refreshOverview = async () => {
    const [summaryResponse, modelResponse, auditResponse, healthResponse, inventoryResponse, accountsResponse] = await Promise.all([
      adminAPI.summary(), adminAPI.modelConfig(), adminAPI.auditLog(30),
      adminAPI.systemHealth(), adminAPI.models(), adminAPI.accounts(),
    ]);
    setSummary(summaryResponse.data);
    setModelData(modelResponse.data);
    setModelForm(modelResponse.data.active?.config || modelResponse.data.defaults || {});
    setAudit(auditResponse.data);
    setSystemHealth(healthResponse.data);
    setModelInventory(inventoryResponse.data);
    setAdminAccounts(accountsResponse.data);
  };

  useEffect(() => {
    setBusy(true);
    Promise.all([loadUsers(''), refreshOverview()])
      .catch(reportError)
      .finally(() => setBusy(false));
    // Initial load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chooseUser = user => {
    setSelected(user);
    setForm(userForm(user));
    setResetLink(null);
    setDiagnostics(null);
    setMessage('');
    setError('');
  };

  const updateForm = (field, value) => setForm(current => ({ ...current, [field]: value }));

  const saveUser = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      const payload = {
        firstName: form.firstName,
        lastName: form.lastName,
        email: form.email,
        movielensUserId: form.movielensUserId === '' ? null : Number(form.movielensUserId),
        favoriteGenres: parseTextList(form.favoriteGenres),
        favoriteMovies: parseIdList(form.favoriteMovies),
        watchedMovies: parseIdList(form.watchedMovies),
        preferences: {
          includeWatched: form.includeWatched,
          watchingFrequency: form.watchingFrequency,
        },
        isActive: form.isActive,
      };
      const response = await adminAPI.updateUser(selected.id, payload);
      setSelected(response.data);
      setForm(userForm(response.data));
      setMessage('User attributes saved.');
      await Promise.all([loadUsers(), refreshOverview()]);
    } catch (err) {
      reportError(err);
    } finally {
      setBusy(false);
    }
  };

  const createReset = async () => {
    if (!window.confirm(`Create a password-reset link for ${selected.email}?`)) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await adminAPI.resetPassword(selected.id);
      setResetLink(response.data);
      setMessage('Password-reset link created.');
      await refreshOverview();
    } catch (err) {
      reportError(err);
    } finally {
      setBusy(false);
    }
  };

  const loadDiagnostics = async () => {
    setLoadingDiagnostics(true); setError('');
    try {
      const [profile, recommendations] = await Promise.all([
        adminAPI.mlProfile(selected.id), adminAPI.recommendations(selected.id, 5),
      ]);
      setDiagnostics({ profile: profile.data, recommendations: recommendations.data });
    } catch (err) {
      reportError(err);
    } finally {
      setLoadingDiagnostics(false);
    }
  };

  const saveModel = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      const config = Object.fromEntries(
        MODEL_FIELDS.map(([field]) => [field, Number(modelForm[field])])
      );
      await adminAPI.createModelConfig({ config, reason: modelReason, activate: true });
      setModelReason('');
      setMessage('A new active model configuration was created.');
      await refreshOverview();
    } catch (err) {
      reportError(err);
    } finally {
      setBusy(false);
    }
  };

  const activateVersion = async id => {
    setBusy(true); setError('');
    try {
      await adminAPI.activateModelConfig(id);
      setMessage(`Model configuration ${id} activated.`);
      await refreshOverview();
    } catch (err) {
      reportError(err);
    } finally {
      setBusy(false);
    }
  };

  const runOperation = async (name, action, successMessage) => {
    setOperation(name); setError(''); setMessage('');
    try {
      const response = await action();
      setMessage(successMessage(response?.data));
      await refreshOverview();
    } catch (err) {
      reportError(err);
    } finally {
      setOperation('');
    }
  };

  const checkTmdb = () => runOperation(
    'tmdb', adminAPI.checkTmdb,
    data => data.probe?.healthy
      ? `TMDB responded in ${data.probe.latencyMs} ms.`
      : (data.probe?.message || 'TMDB health check failed.'),
  );

  const clearTmdbCache = () => runOperation(
    'cache', adminAPI.clearTmdbCache,
    data => `Cleared ${data.entriesRemoved} cached TMDB entries.`,
  );

  const verifyModels = () => runOperation(
    'models', adminAPI.verifyModels,
    data => `Verified ${data.models.filter(model => model.available).length} model components.`,
  );

  const refreshSystem = () => runOperation(
    'refresh', () => Promise.resolve({ data: null }),
    () => 'Operational status refreshed.',
  );

  const search = async event => {
    event.preventDefault();
    setBusy(true); setError('');
    try { await loadUsers(query); } catch (err) { reportError(err); }
    finally { setBusy(false); }
  };

  return (
    <div className="admin-shell page-enter">
      <nav className="admin-console-bar">
        <div><strong>MRE</strong><span>Operations Console</span></div>
        <div className="admin-session">
          <span>{admin?.displayName}</span>
          <small>{admin?.email}</small>
          <Link to="/" className="btn btn-ghost btn-sm">Application</Link>
          <button className="btn btn-outline btn-sm" onClick={logout}>Sign out</button>
        </div>
      </nav>
      <main className="admin-page">
        <header className="admin-header">
          <div>
            <div className="admin-eyebrow">Administration</div>
            <h1>Admin Center</h1>
            <p>Monitor services, manage accounts, inspect recommendation signals, and version serving controls.</p>
          </div>
          <span className={`admin-status ${summary?.integrations?.tmdb?.configured ? 'ok' : ''}`}>
            TMDB {summary?.integrations?.tmdb?.configured ? 'configured' : 'not configured'}
          </span>
        </header>

        {error && <div className="error-banner admin-banner">{error}</div>}
        {message && <div className="admin-success admin-banner">{message}</div>}

        <section className="admin-stats">
          <div className="admin-stat"><span>Total users</span><strong>{summary?.users?.total ?? '-'}</strong></div>
          <div className="admin-stat"><span>Isolated admins</span><strong>{summary?.administrators?.active ?? '-'}</strong></div>
          <div className="admin-stat"><span>Inactive</span><strong>{summary?.users?.inactive ?? '-'}</strong></div>
          <div className="admin-stat"><span>Pending resets</span><strong>{summary?.users?.passwordResetPending ?? '-'}</strong></div>
        </section>

        <section className="admin-section">
          <div className="admin-section-head">
            <div><h2>System operations</h2><p>Live service state and controlled diagnostic actions.</p></div>
            <button className="btn btn-secondary btn-sm" onClick={refreshSystem} disabled={Boolean(operation)}>
              {operation === 'refresh' ? 'Refreshing...' : 'Refresh status'}
            </button>
          </div>
          <div className="admin-health-grid">
            <article className={`admin-health-card ${systemHealth?.api?.healthy ? 'ok' : 'bad'}`}>
              <span>Backend API</span><strong>{systemHealth?.api?.healthy ? 'Healthy' : 'Unavailable'}</strong>
              <small>Uptime {systemHealth?.api?.uptimeSeconds ?? '-'} seconds</small>
              <small>Python {systemHealth?.api?.python || '-'}</small>
            </article>
            <article className={`admin-health-card ${systemHealth?.database?.healthy ? 'ok' : 'bad'}`}>
              <span>Database</span><strong>{systemHealth?.database?.healthy ? 'Healthy' : 'Unavailable'}</strong>
              <small>Query latency {systemHealth?.database?.latencyMs ?? '-'} ms</small>
            </article>
            <article className={`admin-health-card ${systemHealth?.tmdb?.lastCheck?.healthy ? 'ok' : ''}`}>
              <span>TMDB API</span><strong>{systemHealth?.tmdb?.configured ? 'Configured' : 'Disabled'}</strong>
              <small>Authentication {systemHealth?.tmdb?.authentication || '-'}</small>
              <small>Last probe {systemHealth?.tmdb?.lastCheck?.latencyMs ?? '-'} ms</small>
            </article>
            <article className={`admin-health-card ${systemHealth?.models?.artifactsAvailable ? 'ok' : ''}`}>
              <span>Model artifacts</span><strong>{systemHealth?.models?.artifactsLoaded ? 'Loaded' : 'Lazy loaded'}</strong>
              <small>{systemHealth?.models?.trainingUsers?.toLocaleString() || '-'} training users</small>
              <small>{systemHealth?.models?.trainingMovies?.toLocaleString() || '-'} training movies</small>
            </article>
          </div>
          <div className="admin-actions">
            <button className="btn btn-primary btn-sm" onClick={checkTmdb} disabled={Boolean(operation)}>
              {operation === 'tmdb' ? 'Checking TMDB...' : 'Run TMDB health check'}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={verifyModels} disabled={Boolean(operation)}>
              {operation === 'models' ? 'Loading models...' : 'Load and verify models'}
            </button>
            <button className="btn btn-outline btn-sm" onClick={clearTmdbCache} disabled={Boolean(operation)}>
              {operation === 'cache' ? 'Clearing...' : 'Clear TMDB cache'}
            </button>
          </div>
          <div className="admin-technical-grid">
            <div><span>TMDB cache</span><strong>{systemHealth?.tmdb?.cache?.entries ?? 0} / {systemHealth?.tmdb?.cache?.maximumEntries ?? '-'}</strong></div>
            <div><span>Request timeout</span><strong>{systemHealth?.tmdb?.timeoutSeconds ?? '-'} s</strong></div>
            <div><span>TMDB workers</span><strong>{systemHealth?.tmdb?.workers ?? '-'}</strong></div>
            <div><span>Admin accounts</span><strong>{adminAccounts.length}</strong></div>
          </div>
          <div className="admin-account-list">
            {adminAccounts.map(account => <div key={account.id}>
              <span><strong>{account.displayName}</strong><small>{account.email}</small></span>
              <span className={`admin-pill ${account.isActive ? 'ok' : ''}`}>
                {account.isActive ? 'Active' : 'Inactive'}
              </span>
              <small>Last login {account.lastLoginAt ? new Date(account.lastLoginAt).toLocaleString() : 'Never'}</small>
            </div>)}
          </div>
        </section>

        <section className="admin-section">
          <div className="admin-section-head">
            <div><h2>Models in service</h2><p>The complete live recommendation pipeline and its artifact state.</p></div>
          </div>
          <div className="admin-pipeline">
            {(modelInventory.pipeline || []).map((stage, index) => (
              <React.Fragment key={stage}>
                <span>{stage.replace(/_/g, ' ')}</span>
                {index < modelInventory.pipeline.length - 1 && <b>→</b>}
              </React.Fragment>
            ))}
          </div>
          <div className="admin-model-inventory">
            {(modelInventory.models || []).map(model => (
              <article key={model.key} className="admin-model-card">
                <div className="admin-model-card-head">
                  <div><h3>{model.name}</h3><span>{model.category}</span></div>
                  <span className={`admin-pill ${model.available ? 'ok' : ''}`}>
                    {model.available ? (model.loaded ? 'Loaded' : 'Available') : 'Missing'}
                  </span>
                </div>
                <p>{model.purpose}</p>
                <dl>{Object.entries(model.configuration || {}).map(([key, value]) => (
                  <div key={key}><dt>{key}</dt><dd>{value ?? '-'}</dd></div>
                ))}</dl>
                {!!model.artifacts?.length && <details>
                  <summary>{model.artifacts.length} artifacts</summary>
                  {model.artifacts.map(file => <div className="admin-artifact" key={file.name}>
                    <span>{file.name}</span><small>{file.present ? `${(file.sizeBytes / 1048576).toFixed(1)} MB` : 'Missing'}</small>
                  </div>)}
                </details>}
              </article>
            ))}
          </div>
        </section>

        <section className="admin-section">
          <div className="admin-section-head">
            <div><h2>Users</h2><p>{totalUsers} accounts</p></div>
            <form className="admin-search" onSubmit={search}>
              <input className="input" value={query} onChange={event => setQuery(event.target.value)}
                placeholder="Search name or email" />
              <button className="btn btn-secondary btn-sm" disabled={busy}>Search</button>
            </form>
          </div>
          <div className="admin-user-layout">
            <div className="admin-user-list">
              {users.map(user => (
                <button key={user.id} className={`admin-user-row ${selected?.id === user.id ? 'selected' : ''}`}
                  onClick={() => chooseUser(user)}>
                  <span className="admin-user-avatar">{user.firstName?.[0]}{user.lastName?.[0]}</span>
                  <span><strong>{user.firstName} {user.lastName}</strong><small>{user.email}</small></span>
                  <span className={`admin-pill ${user.isActive ? 'ok' : ''}`}>{user.isActive ? 'Active' : 'Inactive'}</span>
                </button>
              ))}
              {!users.length && <div className="admin-empty">No users found.</div>}
            </div>

            <div className="admin-user-editor">
              {!form ? <div className="admin-empty">Select a user to inspect and edit.</div> : (
                <>
                  <div className="admin-editor-title">
                    <div><h3>{selected.firstName} {selected.lastName}</h3><span>User #{selected.id}</span></div>
                  </div>
                  <div className="admin-form-grid">
                    <label>First name<input className="input" value={form.firstName} onChange={e => updateForm('firstName', e.target.value)} /></label>
                    <label>Last name<input className="input" value={form.lastName} onChange={e => updateForm('lastName', e.target.value)} /></label>
                    <label className="wide">Email<input className="input" type="email" value={form.email} onChange={e => updateForm('email', e.target.value)} /></label>
                    <label>MovieLens user ID<input className="input" type="number" value={form.movielensUserId} onChange={e => updateForm('movielensUserId', e.target.value)} /></label>
                    <label>Watching frequency<select className="input" value={form.watchingFrequency} onChange={e => updateForm('watchingFrequency', e.target.value)}>
                      <option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option>
                    </select></label>
                    <label className="wide">Favorite genres<textarea className="input admin-textarea" value={form.favoriteGenres} onChange={e => updateForm('favoriteGenres', e.target.value)} /></label>
                    <label className="wide">Favorite TMDB IDs<textarea className="input admin-textarea" value={form.favoriteMovies} onChange={e => updateForm('favoriteMovies', e.target.value)} /></label>
                    <label className="wide">Watched TMDB IDs<textarea className="input admin-textarea" value={form.watchedMovies} onChange={e => updateForm('watchedMovies', e.target.value)} /></label>
                  </div>
                  <div className="admin-checks">
                    <label><input type="checkbox" checked={form.includeWatched} onChange={e => updateForm('includeWatched', e.target.checked)} /> Include watched titles</label>
                    <label><input type="checkbox" checked={form.isActive} onChange={e => updateForm('isActive', e.target.checked)} /> Account active</label>
                  </div>
                  <div className="admin-actions">
                    <button className="btn btn-primary btn-sm" onClick={saveUser} disabled={busy}>Save user</button>
                    <button className="btn btn-outline btn-sm" onClick={createReset} disabled={busy}>Create reset link</button>
                    <button className="btn btn-secondary btn-sm" onClick={loadDiagnostics} disabled={loadingDiagnostics}>
                      {loadingDiagnostics ? 'Loading model data...' : 'Load ML diagnostics'}
                    </button>
                  </div>
                  {resetLink && <div className="admin-reset-result">
                    <strong>One-time reset link</strong>
                    <textarea className="input admin-textarea" readOnly value={resetLink.resetUrl} />
                    <small>Expires {new Date(resetLink.expiresAt).toLocaleString()}</small>
                  </div>}
                  {diagnostics && <div className="admin-diagnostics">
                    <h3>ML profile</h3>
                    <div className="admin-diagnostic-grid">
                      <div><span>Mapped</span><strong>{diagnostics.profile.mapped ? 'Yes' : 'No'}</strong></div>
                      <div><span>Ratings</span><strong>{diagnostics.profile.ratingCount ?? '-'}</strong></div>
                      <div><span>Mean rating</span><strong>{diagnostics.profile.meanRating ?? '-'}</strong></div>
                      <div><span>Method</span><strong>{diagnostics.profile.similarityMethod || '-'}</strong></div>
                    </div>
                    {diagnostics.profile.message && <p>{diagnostics.profile.message}</p>}
                    {!!diagnostics.profile.similarUsers?.length && <table className="admin-table"><thead><tr><th>MovieLens user</th><th>Similarity</th></tr></thead><tbody>
                      {diagnostics.profile.similarUsers.map(user => <tr key={user.movieLensUserId}><td>{user.movieLensUserId}</td><td>{user.similarity.toFixed(4)}</td></tr>)}
                    </tbody></table>}
                    <h3>Recommendation score preview</h3>
                    <div className="admin-score-list">{diagnostics.recommendations.map(movie => <div key={movie.id}>
                      <span>{movie.title}</span><strong>{movie.recommendationScore?.toFixed(4) ?? '-'}</strong>
                      <small>{Object.entries(movie.scoreComponents || {}).map(([key, value]) => `${key}: ${value ?? 'n/a'}`).join(' | ')}</small>
                    </div>)}</div>
                  </div>}
                </>
              )}
            </div>
          </div>
        </section>

        <section className="admin-section">
          <div className="admin-section-head"><div><h2>Model controls</h2><p>Create an auditable serving configuration.</p></div></div>
          <div className="admin-model-grid">
            {MODEL_FIELDS.map(([field, label, step]) => <label key={field}>{label}
              <input className="input" type="number" step={step} value={modelForm[field] ?? ''}
                onChange={e => setModelForm(current => ({ ...current, [field]: e.target.value }))} />
            </label>)}
            <label className="wide">Change reason<input className="input" value={modelReason} onChange={e => setModelReason(e.target.value)} placeholder="Why is this configuration changing?" /></label>
          </div>
          <div className="admin-actions"><button className="btn btn-primary btn-sm" onClick={saveModel} disabled={busy}>Create and activate version</button></div>
          <table className="admin-table"><thead><tr><th>Version</th><th>Created</th><th>Reason</th><th>Status</th><th /></tr></thead><tbody>
            {(modelData.versions || []).map(version => <tr key={version.id}><td>#{version.id}</td><td>{new Date(version.createdAt).toLocaleString()}</td><td>{version.reason || '-'}</td><td>{version.isActive ? 'Active' : 'Inactive'}</td><td>{!version.isActive && <button className="btn btn-ghost btn-sm" onClick={() => activateVersion(version.id)}>Activate</button>}</td></tr>)}
          </tbody></table>
        </section>

        <section className="admin-section">
          <div className="admin-section-head"><div><h2>Audit log</h2><p>Recent administrative changes.</p></div></div>
          <table className="admin-table"><thead><tr><th>Time</th><th>Administrator</th><th>Action</th><th>Target</th><th>Details</th></tr></thead><tbody>
            {audit.map(event => <tr key={event.id}><td>{new Date(event.createdAt).toLocaleString()}</td><td>{event.adminName || event.adminId}</td><td>{event.action}</td><td>{event.targetName || event.targetUserId || '-'}</td><td>{JSON.stringify(event.details)}</td></tr>)}
          </tbody></table>
        </section>
      </main>
    </div>
  );
}
