import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import MovieCard from '../components/MovieCard';
import PosterImage from '../components/PosterImage';
import { SkeletonRow } from '../components/SkeletonCard';
import { moviesAPI, userAPI } from '../api/api';
import { useAuth } from '../context/AuthContext';

export default function MovieDetailsPage() {
  const { id }      = useParams();
  const navigate    = useNavigate();
  const { user, refreshUser } = useAuth();

  const [movie, setMovie]     = useState(null);
  const [similar, setSimilar] = useState([]);
  const [simLoading, setSimLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [watchLoading, setWatchLoading] = useState(false);
  const [watchMsg, setWatchMsg] = useState('');

  const isWatched = user?.watchedMovies?.includes(Number(id));

  useEffect(() => {
    window.scrollTo(0, 0);
    setLoading(true);
    setSimLoading(true);
    setWatchMsg('');

    moviesAPI.getById(id)
      .then(r => setMovie(r.data))
      .catch(() => setMovie(null))
      .finally(() => setLoading(false));

    moviesAPI.similar(id, 12)
      .then(r => setSimilar(r.data))
      .catch(() => setSimilar([]))
      .finally(() => setSimLoading(false));
  }, [id]);

  const handleWatch = async () => {
    if (!user) { navigate('/login'); return; }
    setWatchLoading(true);
    try {
      if (isWatched) {
        await userAPI.removeWatched(Number(id));
        setWatchMsg('Removed from watched');
      } else {
        await userAPI.markWatched(Number(id));
        setWatchMsg('Marked as watched ✓');
      }
      await refreshUser();
    } catch (_) {
      setWatchMsg('Could not update');
    } finally {
      setWatchLoading(false);
      setTimeout(() => setWatchMsg(''), 3000);
    }
  };

  if (loading) return (
    <div style={{ paddingTop: 64 }}>
      <Navbar />
      <div style={{ height: 480, background: 'var(--bg-2)' }} className="skeleton" />
    </div>
  );

  if (!movie) return (
    <div style={{ paddingTop: 80, textAlign: 'center' }}>
      <Navbar />
      <div className="empty-state">
        <div className="empty-state-icon">🎬</div>
        <div className="empty-state-title">Movie not found</div>
        <button className="btn btn-outline" style={{ marginTop: 16 }} onClick={() => navigate(-1)}>Go back</button>
      </div>
    </div>
  );

  return (
    <div className="details page-enter">
      <Navbar />

      {/* ── Backdrop hero ── */}
      <div className="details-hero">
        <div
          className="details-hero-bg"
          style={{
            backgroundImage: movie.backdrop_url ? `url(${movie.backdrop_url})` : 'none',
            background: !movie.backdrop_url ? 'linear-gradient(135deg,#1a0a1e,#0d0d20)' : undefined,
          }}
        />
        <div className="details-hero-grad" />
        <div className="details-hero-content">
          <h1 style={{ fontSize: 'clamp(24px, 4vw, 48px)', fontWeight: 900 }}>{movie.title}</h1>
          {movie.tagline && <p style={{ fontStyle: 'italic', color: 'var(--text-2)', marginTop: 6 }}>{movie.tagline}</p>}
        </div>
      </div>

      {/* ── Main content ── */}
      <div className="details-body">
        {/* Poster */}
        <div>
          <PosterImage
            src={movie.poster_url}
            alt={`${movie.title} poster`}
            className="details-poster"
            loading="eager"
            fallback={(
              <div
                className="details-poster-fb"
                role="img"
                aria-label={`${movie.title} poster unavailable`}
              >
                {movie.title?.[0]}
              </div>
            )}
          />
        </div>

        {/* Info */}
        <div>
          <div className="details-meta-row">
            {movie.vote_average > 0 && <span className="details-rating">★ {movie.vote_average.toFixed(1)}</span>}
            {movie.year        && <span>{movie.year}</span>}
            {movie.runtime     && <span>{movie.runtime} min</span>}
            {movie.vote_count  > 0 && <span>{movie.vote_count.toLocaleString()} ratings</span>}
          </div>

          {movie.genres?.length > 0 && (
            <div className="details-section">
              <div className="details-section-label">Genres</div>
              <div className="details-genre-chips">
                {movie.genres.map(g => <span key={g} className="details-genre-chip">{g}</span>)}
              </div>
            </div>
          )}

          {movie.overview && (
            <p className="details-overview">{movie.overview}</p>
          )}

          <div className="details-actions">
            <button
              className={`btn ${isWatched ? 'btn-outline' : 'btn-primary'}`}
              onClick={handleWatch}
              disabled={watchLoading}
            >
              {watchLoading ? '…' : isWatched ? '✓ Watched — Remove' : 'Mark as Watched'}
            </button>
            {watchMsg && <span className="watched-badge">{watchMsg}</span>}
          </div>

          {movie.director && (
            <div className="details-section">
              <div className="details-section-label">Director</div>
              <span className="cast-chip">{movie.director}</span>
            </div>
          )}

          {movie.cast?.length > 0 && (
            <div className="details-section">
              <div className="details-section-label">Cast</div>
              <div className="cast-chips">
                {movie.cast.map(c => <span key={c} className="cast-chip">{c}</span>)}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Similar movies ── */}
      <div style={{ padding: '0 48px 60px' }}>
        <div className="section-hdr" style={{ marginBottom: 14 }}>
          <h2 className="section-title">Similar Films</h2>
        </div>
        {simLoading
          ? <SkeletonRow count={6} />
          : similar.length === 0
            ? <p style={{ color: 'var(--text-2)', fontSize: 14 }}>No similar films found.</p>
            : <div className="scroll-row">
                {similar.map(m => <MovieCard key={m.id} movie={m} />)}
              </div>
        }
      </div>
    </div>
  );
}
