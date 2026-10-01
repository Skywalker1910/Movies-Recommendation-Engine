import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowLeft, Star, X, Film } from 'lucide-react';
import { moviesAPI } from '../api/api';
import PosterImage from '../components/PosterImage';
import MovieCard from '../components/MovieCard';
import { SkeletonRow } from '../components/SkeletonCard';
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL ?? '';

const GENRES = [
  'Action', 'Adventure', 'Animation', 'Comedy', 'Crime',
  'Documentary', 'Drama', 'Family', 'Fantasy', 'History',
  'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction',
  'Thriller', 'War', 'Western',
];

const STEPS = ['Pick Genres', 'Pick Movies', 'Your Recommendations'];

function StepIndicator({ step }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
      {STEPS.map((label, i) => (
        <React.Fragment key={label}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            color: i <= step ? 'var(--red)' : 'var(--text-3)',
            fontWeight: i === step ? 700 : 400, fontSize: 13,
          }}>
            <span style={{
              width: 24, height: 24, borderRadius: '50%', display: 'inline-flex',
              alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700,
              background: i <= step ? 'var(--red)' : 'var(--bg-3)',
              color: i <= step ? '#fff' : 'var(--text-3)',
            }}>{i + 1}</span>
            <span className="preview-step-label">{label}</span>
          </div>
          {i < STEPS.length - 1 && (
            <div style={{ flex: 1, height: 1, background: i < step ? 'var(--red)' : 'var(--border)', maxWidth: 60 }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

export default function PreviewPage() {
  const isEmbed = new URLSearchParams(window.location.search).get('embed') === 'true';
  const [step, setStep] = useState(0);

  const [genres, setGenres] = useState([]);
  const [movieSearch, setMovieSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [favMovies, setFavMovies] = useState([]);
  const [searching, setSearching] = useState(false);

  const [recs, setRecs] = useState([]);
  const [recsLoading, setRecsLoading] = useState(false);

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

  const fetchRecs = async () => {
    setStep(2);
    setRecsLoading(true);
    try {
      const res = await axios.post(`${BASE_URL}/movies/preview`, {
        genres,
        movieIds: favMovies.map(m => m.id),
        n: 12,
      });
      setRecs(res.data);
    } catch (_) {
      setRecs([]);
    } finally {
      setRecsLoading(false);
    }
  };

  return (
    <div className={`preview-page page-enter ${isEmbed ? 'preview-embed' : ''}`}>
      {!isEmbed && (
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 32px' }}>
          <Link to="/" style={{ fontSize: 22, fontWeight: 900, color: 'var(--red)', textDecoration: 'none' }}>MRE</Link>
          <div style={{ display: 'flex', gap: 8 }}>
            <Link to="/login" className="btn btn-outline btn-sm">Sign In</Link>
            <Link to="/register" className="btn btn-primary btn-sm">Sign Up</Link>
          </div>
        </header>
      )}

      <div className="preview-container">
        <div className="preview-header">
          <Film size={20} style={{ color: 'var(--red)' }} />
          <h1 style={{ fontSize: 20, fontWeight: 800 }}>Try Movie Recommendations</h1>
          <p style={{ fontSize: 14, color: 'var(--text-2)' }}>
            Pick your taste, get AI-powered picks. No account needed.
          </p>
        </div>

        <StepIndicator step={step} />

        {/* Step 0: Genres */}
        {step === 0 && (
          <div className="preview-step">
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>What genres do you enjoy?</h2>
            <div className="genre-grid">
              {GENRES.map(g => (
                <button
                  key={g} type="button"
                  className={`genre-chip ${genres.includes(g) ? 'selected' : ''}`}
                  onClick={() => toggleGenre(g)}
                >{g}</button>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
              <button className="btn btn-primary" onClick={() => setStep(1)} disabled={genres.length === 0}>
                Next <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Step 1: Movies */}
        {step === 1 && (
          <div className="preview-step">
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>Name some films you love</h2>
            <p style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 12 }}>
              Select up to 5 movies. <span style={{ color: 'var(--red)' }}>{favMovies.length}/5</span>
            </p>
            <input
              className="input" placeholder="Search movies..."
              value={movieSearch}
              onChange={e => setMovieSearch(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            {searching && <p style={{ fontSize: 12, color: 'var(--text-2)' }}>Searching...</p>}
            {favMovies.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {favMovies.map(m => (
                    <button key={m.id} type="button" onClick={() => toggleMovie(m)}
                      style={{ background: 'rgba(229,9,20,.2)', border: '1px solid var(--red)', borderRadius: 100, padding: '4px 12px', fontSize: 12, color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
                    >
                      {m.title} <X size={12} />
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="movie-search-list">
              {searchResults.map(movie => {
                const selected = favMovies.some(m => m.id === movie.id);
                return (
                  <div key={movie.id} className={`movie-search-item ${selected ? 'selected' : ''}`} onClick={() => toggleMovie(movie)}>
                    <PosterImage
                      src={movie.poster_url}
                      alt={`${movie.title} poster`}
                      className="movie-search-thumb"
                      fallback={<div className="movie-search-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 900, color: 'rgba(255,255,255,.2)' }}>{movie.title?.[0]}</div>}
                    />
                    <div className="movie-search-info">
                      <div className="movie-search-title">{movie.title}</div>
                      <div className="movie-search-year">
                        {movie.year} {movie.vote_average > 0 && <><Star size={11} /> {movie.vote_average.toFixed(1)}</>}
                      </div>
                    </div>
                    {selected && <span style={{ color: 'var(--red)' }}><Star size={14} fill="var(--red)" /></span>}
                  </div>
                );
              })}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}>
              <button className="btn btn-outline" onClick={() => setStep(0)}>
                <ArrowLeft size={14} /> Back
              </button>
              <button className="btn btn-primary" onClick={fetchRecs} disabled={favMovies.length === 0}>
                Get Recommendations <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Results */}
        {step === 2 && (
          <div className="preview-step">
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Recommended for you</h2>
            {recsLoading
              ? <SkeletonRow count={6} />
              : recs.length === 0
                ? <p style={{ color: 'var(--text-2)' }}>No recommendations found. Try different movies.</p>
                : <div className="preview-grid">
                    {recs.map(m => <MovieCard key={m.id} movie={m} />)}
                  </div>
            }
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 24 }}>
              <button className="btn btn-outline" onClick={() => { setStep(1); setRecs([]); }}>
                <ArrowLeft size={14} /> Change picks
              </button>
              {!isEmbed && (
                <Link to="/register" className="btn btn-primary">
                  Create account for full experience <ArrowRight size={14} />
                </Link>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
