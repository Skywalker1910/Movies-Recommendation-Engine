import React from 'react';

export default function TmdbAttribution() {
  return (
    <footer className="tmdb-attribution">
      <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer">
        <img src="/tmdb-logo.svg" alt="The Movie Database" />
      </a>
      <p>This product uses the TMDB API but is not endorsed or certified by TMDB.</p>
    </footer>
  );
}
