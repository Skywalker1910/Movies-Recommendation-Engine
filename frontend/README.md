# React Client

This package contains the user interface for the movie recommendation application. It communicates with the Flask API through Axios and stores the current JWT in browser local storage.

## Main routes

| Route | Access | Purpose |
|---|---|---|
| `/` | Public | Project landing page |
| `/login` | Public | Account login |
| `/register` | Public | Registration and preference collection |
| `/dashboard` | Authenticated | Recommendation sections and featured movie |
| `/movie/:id` | Authenticated | Movie metadata and similar titles |
| `/profile` | Authenticated | User settings and watch history |

## Setup

```powershell
npm install
npm start
```

The development server runs at `http://localhost:3000`. The API base URL defaults to `http://localhost:5000` and can be overridden with `REACT_APP_API_URL`.

## Scripts

| Command | Purpose |
|---|---|
| `npm start` | Start the development server |
| `npm test -- --watchAll=false` | Run the test suite once |
| `npm run build` | Create an optimized production build |

## Poster handling

Poster URLs are remote and may be missing or stale. `PosterImage` centralizes image-error handling for cards, registration search results, and movie details. A failed request is replaced with a local styled fallback rather than a broken image element.

## Current tests

The component tests verify that the poster fallback is rendered when:

- no poster URL is available;
- the browser reports an image loading error.

Broader route, authentication, accessibility, and interaction tests remain future work.
