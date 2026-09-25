import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import MovieCard from '../components/MovieCard';
import { SkeletonRow } from '../components/SkeletonCard';
import { moviesAPI } from '../api/api';
import { useAuth } from '../context/AuthContext';

const SECTIONS = [
  { key: 'recommended', title: 'Recommended for You',  accent: true },
  { key: 'favorites',   title: 'Based on Your Favourites', accent: false },
  { key: 'trending',    title: 'Trending Now',          accent: false },
];

function useRecs(section) {
  const [data, setData]   = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    moviesAPI.recommendations(section, 20)
      .then(r => setData(r.data))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [section]);
  return { data, loading };
}

function RecSection({ section, title, accent }) {
  const { data, loading } = useRecs(section);
  return (
    <div className="section">
      <div className="section-hdr">
        <h2 className="section-title">
          {accent ? <><span>✦</span> {title}</> : title}
        </h2>
      </div>
      {loading
        ? <SkeletonRow count={7} />
        : data.length === 0
          ? <p style={{ color: 'var(--text-2)', fontSize: 14 }}>Nothing to show yet — add some favourite films to your profile.</p>
          : <div className="scroll-row">
              {data.map(m => <MovieCard key={m.id} movie={m} />)}
            </div>
      }
    </div>
  );
}

export default function DashboardPage() {
  const navigate    = useNavigate();
  const { user }    = useAuth();
  const [hero, setHero] = useState(null);

  useEffect(() => {
    moviesAPI.trending(1)
      .then(r => r.data[0] && setHero(r.data[0]))
      .catch(() => {});
  }, []);

  return (
    <div className="dashboard page-enter">
      <Navbar />

      {/* ── Hero banner ── */}
      <div className="hero">
        <div
          className="hero-bg"
          style={{ backgroundImage: hero?.backdrop_url ? `url(${hero.backdrop_url})` : 'none', background: !hero?.backdrop_url ? 'linear-gradient(135deg,#1a0a1e,#0d0d20)' : undefined }}
        />
        <div className="hero-grad" />
        <div className="hero-content">
          <div className="hero-badge">Featured Film</div>
          <h1 className="hero-title">{hero?.title ?? 'Your personalised cinema'}</h1>
          <div className="hero-meta">
            {hero?.year   && <span>{hero.year}</span>}
            {hero?.vote_average > 0 && <span>★ {hero.vote_average.toFixed(1)}</span>}
            {hero?.genres?.[0] && <span>{hero.genres[0]}</span>}
          </div>
          {hero?.overview && <p className="hero-overview">{hero.overview}</p>}
          <div className="hero-actions">
            {hero && (
              <button className="btn btn-primary" onClick={() => navigate(`/movie/${hero.id}`)}>
                ▶ More Info
              </button>
            )}
            <button className="btn btn-secondary" onClick={() => navigate('/profile')}>
              My Preferences
            </button>
          </div>
        </div>
      </div>

      {/* ── Recommendation rows ── */}
      <div className="dash-content">
        {user?.firstName && (
          <h2 style={{ fontSize: 15, color: 'var(--text-2)', marginBottom: 32 }}>
            Good to see you back, <strong style={{ color: 'var(--text)' }}>{user.firstName}</strong> 👋
          </h2>
        )}
        {SECTIONS.map(s => (
          <RecSection key={s.key} {...s} />
        ))}
      </div>
    </div>
  );
}
