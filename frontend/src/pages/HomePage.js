import React, { useState, useEffect, useRef } from 'react';
import { getCollaborativeRecommendations, getContentRecommendations, searchMovies } from '../api/api';
import './HomePage.css';

const StarRating = ({ rating }) => {
    const filled = Math.round(rating);
    return (
        <div className="star-rating">
            {[1, 2, 3, 4, 5].map((s) => (
                <span key={s} className={s <= filled ? 'star filled' : 'star'}>★</span>
            ))}
            <span className="rating-num">{rating.toFixed(1)}</span>
        </div>
    );
};

const MovieCard = ({ movie, type, onClick }) => (
    <div className={`movie-card ${onClick ? 'clickable' : ''}`} onClick={onClick}>
        <div className="movie-card-poster">🎬</div>
        <div className="movie-card-body">
            <p className="movie-card-title">{movie.title || `Movie #${movie.movie_id || movie.id}`}</p>
            {type === 'collaborative' && <StarRating rating={movie.predicted_rating} />}
        </div>
    </div>
);

const SkeletonCard = () => (
    <div className="movie-card skeleton">
        <div className="skeleton-poster"></div>
        <div className="skeleton-body">
            <div className="skeleton-line long"></div>
            <div className="skeleton-line short"></div>
        </div>
    </div>
);

const HomePage = ({ userId }) => {
    const [collaborativeRecs, setCollaborativeRecs] = useState([]);
    const [contentRecs, setContentRecs] = useState([]);
    const [searchResults, setSearchResults] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedMovie, setSelectedMovie] = useState(null);
    const [loadingCollab, setLoadingCollab] = useState(true);
    const [loadingContent, setLoadingContent] = useState(false);
    const [loadingSearch, setLoadingSearch] = useState(false);
    const [showDropdown, setShowDropdown] = useState(false);
    const searchRef = useRef(null);
    const debounceRef = useRef(null);

    useEffect(() => {
        getCollaborativeRecommendations(userId).then((data) => {
            setCollaborativeRecs(Array.isArray(data) ? data : []);
            setLoadingCollab(false);
        });
    }, [userId]);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (searchRef.current && !searchRef.current.contains(e.target)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSearchChange = (e) => {
        const q = e.target.value;
        setSearchQuery(q);
        clearTimeout(debounceRef.current);
        if (q.length < 2) { setSearchResults([]); setShowDropdown(false); return; }
        setLoadingSearch(true);
        debounceRef.current = setTimeout(async () => {
            const results = await searchMovies(q);
            setSearchResults(Array.isArray(results) ? results : []);
            setShowDropdown(true);
            setLoadingSearch(false);
        }, 300);
    };

    const handleSelectMovie = async (movie) => {
        setSelectedMovie(movie);
        setSearchQuery(movie.title);
        setShowDropdown(false);
        setSearchResults([]);
        setContentRecs([]);
        setLoadingContent(true);
        const data = await getContentRecommendations(movie.id);
        setContentRecs(Array.isArray(data) ? data : []);
        setLoadingContent(false);
    };

    return (
        <div className="page">
            <header className="app-header">
                <div className="header-inner">
                    <div className="logo">
                        <span className="logo-icon">🎯</span>
                        <span className="logo-text">CineRec</span>
                    </div>
                    <div className="user-pill">👤 User #{userId}</div>
                </div>
            </header>

            <main className="main-content">
                {/* Collaborative Section */}
                <section className="section">
                    <div className="section-header">
                        <h2 className="section-title">⭐ Recommended For You</h2>
                        <p className="section-sub">Based on users with similar taste</p>
                    </div>
                    <div className="cards-row">
                        {loadingCollab
                            ? [...Array(5)].map((_, i) => <SkeletonCard key={i} />)
                            : collaborativeRecs.length > 0
                                ? collaborativeRecs.map((movie) => (
                                    <MovieCard
                                        key={movie.movie_id}
                                        movie={movie}
                                        type="collaborative"
                                        onClick={() => handleSelectMovie({ id: movie.movie_id, title: movie.title })}
                                    />
                                ))
                                : <p className="empty-msg">No recommendations available for this user.</p>
                        }
                    </div>
                </section>

                {/* Content-Based Section */}
                <section className="section">
                    <div className="section-header">
                        <h2 className="section-title">🔍 Find Similar Movies</h2>
                        <p className="section-sub">Type a movie title to discover similar films</p>
                    </div>

                    <div className="search-container" ref={searchRef}>
                        <div className="search-input-wrapper">
                            <span className="search-icon">🔎</span>
                            <input
                                type="text"
                                className="search-input"
                                placeholder="Search movie title..."
                                value={searchQuery}
                                onChange={handleSearchChange}
                                onFocus={() => searchResults.length > 0 && setShowDropdown(true)}
                                autoComplete="off"
                            />
                            {loadingSearch && <span className="search-spinner">⟳</span>}
                        </div>
                        {showDropdown && searchResults.length > 0 && (
                            <ul className="search-dropdown">
                                {searchResults.map((movie) => (
                                    <li
                                        key={movie.id}
                                        className="search-item"
                                        onMouseDown={() => handleSelectMovie(movie)}
                                    >
                                        🎬 <span>{movie.title}</span>
                                        <span className="movie-id-badge">#{movie.id}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>

                    {selectedMovie && (
                        <div className="selected-tag">
                            Showing similar to: <strong>{selectedMovie.title}</strong>
                        </div>
                    )}

                    <div className="cards-row">
                        {loadingContent
                            ? [...Array(5)].map((_, i) => <SkeletonCard key={i} />)
                            : contentRecs.length > 0
                                ? contentRecs.map((movie) => (
                                    <MovieCard
                                        key={movie.id}
                                        movie={movie}
                                        type="content"
                                        onClick={() => handleSelectMovie(movie)}
                                    />
                                ))
                                : selectedMovie
                                    ? <p className="empty-msg">No similar movies found.</p>
                                    : null
                        }
                    </div>
                </section>
            </main>

            <footer className="app-footer">
                <p>CineRec &mdash; Powered by collaborative &amp; content-based filtering</p>
            </footer>
        </div>
    );
};

export default HomePage;

