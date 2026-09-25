import React from 'react';
import { useNavigate } from 'react-router-dom';
import PosterImage from './PosterImage';

// Genre → hue for gradient fallback cards
const GENRE_COLORS = {
  Action: [0, 70], Adventure: [30, 65], Animation: [180, 60], Comedy: [50, 55],
  Crime: [260, 40], Documentary: [200, 50], Drama: [220, 45], Family: [140, 55],
  Fantasy: [280, 60], History: [35, 45], Horror: [0, 35], Music: [310, 55],
  Mystery: [270, 50], Romance: [340, 55], 'Science Fiction': [200, 60],
  Thriller: [240, 45], War: [15, 40], Western: [25, 50],
};

function getFallbackGradient(movie) {
  const genre = (movie.genres || [])[0];
  const [hue, sat] = GENRE_COLORS[genre] || [220, 40];
  return `linear-gradient(160deg, hsl(${hue},${sat}%,18%) 0%, hsl(${hue + 30},${sat - 10}%,10%) 100%)`;
}

export default function MovieCard({ movie }) {
  const navigate = useNavigate();

  if (!movie) return null;

  const initial = (movie.title || '?')[0].toUpperCase();

  return (
    <div className="card" onClick={() => navigate(`/movie/${movie.id}`)}>
      <PosterImage
        src={movie.poster_url}
        alt={`${movie.title} poster`}
        className="card-poster"
        fallback={(
          <div
            className="card-poster-fallback"
            style={{ background: getFallbackGradient(movie) }}
            role="img"
            aria-label={`${movie.title} poster unavailable`}
          >
            <span className="fallback-initial">{initial}</span>
            <div className="fallback-info">
              <div className="fallback-title">{movie.title}</div>
              {movie.year && <div className="fallback-year">{movie.year}</div>}
              {movie.vote_average > 0 && (
                <div className="fallback-rating">★ {movie.vote_average.toFixed(1)}</div>
              )}
            </div>
          </div>
        )}
      />

      {/* Hover overlay */}
      <div className="card-overlay">
        <div className="card-overlay-title">{movie.title}</div>
        <div className="card-overlay-tags">
          {(movie.genres || []).slice(0, 2).map(g => (
            <span key={g} className="card-tag">{g}</span>
          ))}
        </div>
      </div>

      <div className="card-body">
        <div className="card-title">{movie.title}</div>
        <div className="card-meta">
          {movie.vote_average > 0 && (
            <span className="card-rating">★ {movie.vote_average.toFixed(1)}</span>
          )}
          {movie.year && <span>{movie.year}</span>}
        </div>
        {movie.reason && <div className="card-reason">{movie.reason}</div>}
      </div>
    </div>
  );
}
