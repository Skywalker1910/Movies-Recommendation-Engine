import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { moviesAPI } from '../api/api';
import PosterImage from '../components/PosterImage';

const GENRES = [
  'Action', 'Adventure', 'Animation', 'Comedy', 'Crime',
  'Documentary', 'Drama', 'Family', 'Fantasy', 'History',
  'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction',
  'Thriller', 'War', 'Western',
];

const STEPS = ['Account', 'Genres', 'Favourite Films', 'Preferences'];
const TOTAL = STEPS.length;

function StepDots({ step }) {
  return (
    <div>
      <div className="reg-progress">
        {STEPS.map((_, i) => (
          <div
            key={i}
            className={`reg-step ${i < step ? 'done' : i === step ? 'active' : ''}`}
          />
        ))}
      </div>
      <div className="reg-progress-label" style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 4 }}>
        Step {step + 1} of {TOTAL} — {STEPS[step]}
      </div>
    </div>
  );
}

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate      = useNavigate();
  const [step, setStep] = useState(0);
  const [error, setError]   = useState('');
  const [loading, setLoading] = useState(false);

  /* Step 1 */
  const [account, setAccount] = useState({ firstName: '', lastName: '', email: '', password: '', confirm: '' });
  /* Step 2 */
  const [genres, setGenres] = useState([]);
  /* Step 3 */
  const [movieSearch, setMovieSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [favMovies, setFavMovies] = useState([]);
  const [searching, setSearching] = useState(false);
  /* Step 4 */
  const [prefs, setPrefs] = useState({ includeWatched: false, watchingFrequency: 'weekly' });

  /* Movie search debounce */
  const doSearch = useCallback(async q => {
    if (!q.trim()) { setSearchResults([]); return; }
    setSearching(true);
    try {
      const res = await moviesAPI.search(q, 8);
      setSearchResults(res.data);
    } catch (_) {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => doSearch(movieSearch), 350);
    return () => clearTimeout(t);
  }, [movieSearch, doSearch]);

  const toggleGenre = g =>
    setGenres(prev => prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]);

  const toggleMovie = movie => {
    setFavMovies(prev => {
      const has = prev.some(m => m.id === movie.id);
      return has ? prev.filter(m => m.id !== movie.id) : [...prev, movie].slice(0, 5);
    });
  };

  const nextStep = () => {
    setError('');
    if (step === 0) {
      const { firstName, lastName, email, password, confirm } = account;
      if (!firstName || !lastName || !email || !password) { setError('All fields are required.'); return; }
      if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
      if (password !== confirm) { setError('Passwords do not match.'); return; }
    }
    setStep(s => s + 1);
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);
    try {
      await register({
        firstName:         account.firstName,
        lastName:          account.lastName,
        email:             account.email,
        password:          account.password,
        favoriteGenres:    genres,
        favoriteMovies:    favMovies.map(m => m.id),
        includeWatched:    prefs.includeWatched,
        watchingFrequency: prefs.watchingFrequency,
      });
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err.response?.data?.error || 'Registration failed.');
      setStep(0);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-bg page-enter">
      <div className="auth-card" style={{ maxWidth: step === 2 ? 480 : 420 }}>
        <div className="auth-logo">CineMatch</div>
        <StepDots step={step} />

        {error && <div className="auth-error" style={{ marginBottom: 16 }}>{error}</div>}

        {/* ── Step 0: Account ── */}
        {step === 0 && (
          <>
            <h2 className="auth-title" style={{ marginBottom: 20 }}>Create your account</h2>
            <div className="auth-form">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="field">
                  <label>First name</label>
                  <input className="input" placeholder="Alex" value={account.firstName}
                    onChange={e => setAccount(a => ({ ...a, firstName: e.target.value }))} />
                </div>
                <div className="field">
                  <label>Last name</label>
                  <input className="input" placeholder="Smith" value={account.lastName}
                    onChange={e => setAccount(a => ({ ...a, lastName: e.target.value }))} />
                </div>
              </div>
              <div className="field">
                <label>Email</label>
                <input type="email" className="input" placeholder="you@example.com"
                  value={account.email}
                  onChange={e => setAccount(a => ({ ...a, email: e.target.value }))} />
              </div>
              <div className="field">
                <label>Password</label>
                <input type="password" className="input" placeholder="Min. 8 characters"
                  value={account.password}
                  onChange={e => setAccount(a => ({ ...a, password: e.target.value }))} />
              </div>
              <div className="field">
                <label>Confirm password</label>
                <input type="password" className="input" placeholder="Repeat password"
                  value={account.confirm}
                  onChange={e => setAccount(a => ({ ...a, confirm: e.target.value }))}
                  onKeyDown={e => e.key === 'Enter' && nextStep()} />
              </div>
            </div>
          </>
        )}

        {/* ── Step 1: Genres ── */}
        {step === 1 && (
          <>
            <h2 className="auth-title" style={{ marginBottom: 6 }}>What do you like to watch?</h2>
            <p style={{ fontSize: 14, color: 'var(--text-2)', marginBottom: 18 }}>Pick any genres that interest you.</p>
            <div className="genre-grid">
              {GENRES.map(g => (
                <button
                  key={g} type="button"
                  className={`genre-chip ${genres.includes(g) ? 'selected' : ''}`}
                  onClick={() => toggleGenre(g)}
                >{g}</button>
              ))}
            </div>
          </>
        )}

        {/* ── Step 2: Favourite Movies ── */}
        {step === 2 && (
          <>
            <h2 className="auth-title" style={{ marginBottom: 6 }}>Name some films you love</h2>
            <p style={{ fontSize: 14, color: 'var(--text-2)', marginBottom: 14 }}>
              Search and select up to 5 movies. <span style={{ color: 'var(--red)' }}>{favMovies.length}/5 selected</span>
            </p>
            <input
              className="input" placeholder="Search movies…"
              value={movieSearch}
              onChange={e => setMovieSearch(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            {searching && <p style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 6 }}>Searching…</p>}
            {favMovies.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 6, fontWeight: 600 }}>SELECTED</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {favMovies.map(m => (
                    <button key={m.id} type="button"
                      onClick={() => toggleMovie(m)}
                      style={{ background: 'rgba(229,9,20,.2)', border: '1px solid var(--red)', borderRadius: 100, padding: '4px 12px', fontSize: 12, color: '#fff', cursor: 'pointer' }}
                    >
                      {m.title} ✕
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="movie-search-list">
              {searchResults.map(movie => {
                const selected = favMovies.some(m => m.id === movie.id);
                return (
                  <div
                    key={movie.id}
                    className={`movie-search-item ${selected ? 'selected' : ''}`}
                    onClick={() => toggleMovie(movie)}
                  >
                    <PosterImage
                      src={movie.poster_url}
                      alt={`${movie.title} poster`}
                      className="movie-search-thumb"
                      fallback={(
                        <div
                          className="movie-search-thumb"
                          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 900, color: 'rgba(255,255,255,.2)' }}
                          role="img"
                          aria-label={`${movie.title} poster unavailable`}
                        >
                          {movie.title?.[0]}
                        </div>
                      )}
                    />
                    <div className="movie-search-info">
                      <div className="movie-search-title">{movie.title}</div>
                      <div className="movie-search-year">{movie.year} {movie.vote_average > 0 && `· ★ ${movie.vote_average.toFixed(1)}`}</div>
                    </div>
                    {selected && <span style={{ color: 'var(--red)', fontWeight: 700 }}>✓</span>}
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* ── Step 3: Preferences ── */}
        {step === 3 && (
          <>
            <h2 className="auth-title" style={{ marginBottom: 20 }}>Viewing preferences</h2>
            <div className="auth-form">
              <div className="field">
                <label>How often do you watch?</label>
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
                  <div style={{ fontWeight: 600, fontSize: 14 }}>Include watched films</div>
                  <div style={{ fontSize: 12, color: 'var(--text-2)' }}>Re-recommend movies you have already seen</div>
                </div>
              </label>
            </div>
          </>
        )}

        {/* Navigation buttons */}
        <div style={{ display: 'flex', gap: 10, marginTop: 28 }}>
          {step > 0 && (
            <button type="button" className="btn btn-outline" onClick={() => setStep(s => s - 1)}>
              Back
            </button>
          )}
          <button
            type="button" className="btn btn-primary" style={{ flex: 1 }}
            onClick={step === TOTAL - 1 ? handleSubmit : nextStep}
            disabled={loading}
          >
            {loading ? 'Creating account…' : step === TOTAL - 1 ? 'Launch CineMatch 🚀' : 'Continue'}
          </button>
        </div>

        {step === 0 && (
          <p className="auth-switch">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        )}
      </div>
    </div>
  );
}
