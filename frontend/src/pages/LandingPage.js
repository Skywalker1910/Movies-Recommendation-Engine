import React from 'react';
import { Link } from 'react-router-dom';

const FEATURES = [
  { icon: '🎯', title: 'Personalised Picks', desc: 'Hybrid AI blends collaborative filtering and content similarity for spot-on recommendations.' },
  { icon: '🔥', title: 'Trending Now', desc: 'Bayesian popularity scoring surfaces films that are genuinely great, not just viral.' },
  { icon: '📚', title: 'Watch History', desc: 'Track what you have seen and keep your recommendations fresh and relevant.' },
  { icon: '🎬', title: '45 000+ Titles', desc: 'Built on the full MovieLens & TMDB dataset — from silent films to today\'s blockbusters.' },
];

export default function LandingPage() {
  return (
    <div className="landing page-enter">
      {/* Minimal top bar */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 48px' }}>
        <span style={{ fontSize: 22, fontWeight: 900, color: 'var(--red)' }}>MRE</span>
        <Link to="/login" className="btn btn-outline btn-sm">Sign In</Link>
      </header>

      {/* Hero */}
      <section className="landing-hero">
        <span className="landing-badge">AI-Powered · Open Source</span>
        <h1 className="landing-title">
          Your next favourite<br />
          film is one click <span className="accent">away.</span>
        </h1>
        <p className="landing-sub">
          Movie Recommendation Engine uses a hybrid neural model — FunkSVD, NeuMF, and TF-IDF
          content signals — to surface movies you will actually love.
        </p>
        <div className="landing-cta">
          <Link to="/register" className="btn btn-primary btn-lg">Get Started — it's free</Link>
          <Link to="/login" className="btn btn-secondary btn-lg">Sign In</Link>
        </div>
      </section>

      {/* Features */}
      <div className="landing-features">
        {FEATURES.map(f => (
          <div key={f.title} className="feature-card">
            <div className="feature-icon">{f.icon}</div>
            <div className="feature-title">{f.title}</div>
            <div className="feature-desc">{f.desc}</div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <footer style={{ textAlign: 'center', padding: '24px', fontSize: 13, color: 'var(--text-3)' }}>
        Built with Flask · React · scikit-learn · PyTorch
      </footer>
    </div>
  );
}
