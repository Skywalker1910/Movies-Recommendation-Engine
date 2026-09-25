# Movie Recommendation Web Application

This directory contains the application layer for the recommendation study. A Flask API serves movie metadata, user accounts, and model-backed recommendations. A React client provides registration, authentication, profile management, browsing, and recommendation views.

The application is a research prototype. It demonstrates how the notebook artifacts can be integrated into a usable system; it is not presented as a production deployment.

## Architecture

```text
React client
    |
    | HTTP and JWT
    v
Flask application
    |-- authentication and user profiles
    |-- movie search and metadata
    |-- recommendation orchestration
    |
    |-- SQLite for local development
    |-- PostgreSQL through Docker Compose
    |-- serialized artifacts from ../models
```

## Directory structure

```text
movie_recommendation_system/
|-- backend/
|   |-- app/
|   |   |-- auth.py
|   |   |-- user_routes.py
|   |   |-- movie_routes.py
|   |   |-- recommendation_routes.py
|   |   |-- movie_service.py
|   |   |-- ml_service.py
|   |   `-- models.py
|   |-- config.py
|   |-- requirements.txt
|   `-- run.py
|-- frontend/
|   |-- src/
|   |-- package.json
|   `-- package-lock.json
`-- docker-compose.yml
```

## Local development

Create and activate the shared Python environment from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create the backend configuration:

```powershell
Copy-Item movie_recommendation_system\backend\.env.example `
  movie_recommendation_system\backend\.env
```

Set development secrets in `backend/.env`, then start the API:

```powershell
Set-Location movie_recommendation_system\backend
python run.py
```

Start the frontend in a second terminal:

```powershell
Set-Location movie_recommendation_system\frontend
npm install
npm start
```

| Service | Address |
|---|---|
| React client | `http://localhost:3000` |
| Flask API | `http://localhost:5000` |
| Health check | `http://localhost:5000/health` |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `FLASK_ENV` | `development` | Selects development, testing, or production settings |
| `SECRET_KEY` | Development placeholder | Flask secret; replace outside local development |
| `JWT_SECRET_KEY` | Development placeholder | JWT signing key; replace outside local development |
| `JWT_EXPIRES_HOURS` | `24` | Access-token lifetime |
| `DATABASE_URL` | Local SQLite | SQLAlchemy database connection |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed client origins |
| `ADMIN_JWT_SECRET_KEY` | Development placeholder | Separate administrator-token signing key |
| `ADMIN_SESSION_HOURS` | `4` | Administrator-session lifetime |
| `FRONTEND_URL` | `http://localhost:3000` | Base URL used for password-reset links |
| `PASSWORD_RESET_MINUTES` | `30` | Lifetime of administrator-issued reset links |
| `MODELS_DIR` | Repository `models/` | Optional artifact-directory override |
| `TMDB_API_KEY` | Empty | TMDB API v3 developer key used by the backend |
| `TMDB_READ_TOKEN` | Empty | Optional bearer token; takes precedence over the API key |
| `TMDB_LANGUAGE` | `en-US` | Language for live movie metadata |
| `TMDB_CACHE_TTL_SECONDS` | `86400` | Successful response cache lifetime |
| `TMDB_MAX_WORKERS` | `8` | Maximum concurrent requests while enriching lists |
| `PORT` | `5000` | Backend port |

Do not commit `backend/.env`.

### TMDB integration

The recommendation models continue to use the local MovieLens and TMDB snapshot so that experiments remain reproducible. Before movie results reach the client, the Flask service requests current TMDB metadata and merges it over the local record. The live response supplies current poster and backdrop paths, title, overview, release date, runtime, genres, votes, cast, director, IMDb ID, and production information.

Requests are cached in memory for 24 hours by default. Failed requests are cached for five minutes. Search, batch, trending, and recommendation results are enriched concurrently, with a default limit of eight requests at a time. If TMDB is unavailable, the service returns the local record and the React client retains its image fallback.

The health response reports `integrations.tmdb` as `configured` or `disabled` without exposing the credential. The React client contains no TMDB secret.

Verify the credential and one poster response from the backend directory:

```powershell
python -m scripts.check_tmdb
```

TMDB requires attribution. The client includes an approved TMDB logo and the required notice. Review the [TMDB API terms](https://www.themoviedb.org/api-terms-of-use) before public deployment; the current terms contain separate restrictions for applications associated with machine learning or artificial intelligence.

## API surface

### Authentication

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/auth/register` | Create an account and return a JWT |
| `POST` | `/auth/login` | Authenticate and return a JWT |
| `GET` | `/auth/me` | Return the current user |
| `POST` | `/auth/reset-password` | Consume a one-time reset token |

### User profile

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/user/profile` | Retrieve profile preferences |
| `PUT` | `/user/profile` | Update genres, favorite movies, and preferences |
| `PUT` | `/user/password` | Change the current password |
| `POST` | `/user/watch` | Add a movie to watch history |
| `DELETE` | `/user/watch/<movie_id>` | Remove a movie from watch history |

### Movies and recommendations

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/movies/search?q=<query>` | Search the local catalog |
| `GET` | `/movies/trending` | Return Bayesian-ranked movies |
| `GET` | `/movies/<tmdb_id>` | Return one movie |
| `POST` | `/movies/batch` | Return multiple movies |
| `GET` | `/movies/similar/<tmdb_id>` | Return content-based matches |
| `GET` | `/movies/recommendations` | Return authenticated recommendations |

### Administration

Administration is isolated from the consumer application. Administrators use a separate account table, password, token signing key, browser token, and audit identity. Normal user login never evaluates administrator privileges, user tokens cannot call administration routes, and administrator tokens cannot call user routes. The portal is entered directly at `/admin`.

Provision an administrator independently from the user system. The command prompts for the password without requiring it as a command-line argument:

```powershell
python -m flask --app run:application create-admin
```

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/admin/auth/login` | Authenticate an isolated administrator account |
| `GET` | `/admin/auth/me` | Validate the administrator session |
| `POST` | `/admin/auth/logout` | Revoke the current administrator session |
| `POST` | `/admin/auth/reset-password` | Complete administrator password setup |
| `GET` | `/admin/summary` | Return account, integration, and model status |
| `GET` | `/admin/system/health` | Check API, database, TMDB, and model state |
| `POST` | `/admin/integrations/tmdb/check` | Run a live TMDB configuration probe |
| `DELETE` | `/admin/integrations/tmdb/cache` | Clear the in-memory TMDB cache |
| `GET` | `/admin/models` | Inventory every serving model and artifact |
| `POST` | `/admin/models/verify` | Load and verify the serving pipeline |
| `GET` | `/admin/users` | Search and paginate users |
| `GET`, `PATCH` | `/admin/users/<id>` | View or update controlled user attributes |
| `POST` | `/admin/users/<id>/password-reset` | Create a single-use reset link |
| `GET` | `/admin/users/<id>/ml-profile` | Calculate MovieLens and user-similarity diagnostics |
| `GET` | `/admin/users/<id>/recommendations` | Preview recommendations and score components |
| `GET` | `/admin/model-config` | Return active and previous serving configurations |
| `POST` | `/admin/model-config/versions` | Create a versioned configuration |
| `POST` | `/admin/model-config/versions/<id>/activate` | Roll back or activate a version |
| `GET` | `/admin/audit-log` | Return recent administrator actions |

Passwords and token values are never stored in plain text. A raw reset token is returned once to the administrator; the database stores only its SHA-256 digest. User and model changes are recorded in the audit log.

## Recommendation behavior

Artifacts are loaded lazily on the first recommendation request. The service combines three usable paths:

1. FunkSVD scores for users mapped to MovieLens histories.
2. TF-IDF similarity for favorite-movie seeds.
3. Bayesian popularity and favorite-genre boosts for cold-start users.

NeuMF is optional at runtime. The serving class matches the current checkpoint layout, and the administration model inventory reports its artifact and load state explicitly.

## Database

Local development uses SQLite. The database stores consumer users and isolated administrator accounts separately, along with account-security state, hashed reset tokens, versioned model configuration, and administrator-owned audit events. List and dictionary fields are serialized as JSON text for SQLite and PostgreSQL portability.

Docker Compose starts PostgreSQL 15, the Flask API, and the React development server:

```powershell
Set-Location movie_recommendation_system
docker compose up --build
```

## Verification

The current development baseline has been checked for:

- API health response
- movie search, trending, and similar-movie responses
- in-memory registration, login, and profile access
- expected `401` and `404` responses
- frontend component tests
- administrator authorization, user management, reset-token, and model-version tests
- optimized React build

Run the frontend checks with:

```powershell
Set-Location frontend
$env:CI='true'
npm test -- --watchAll=false
npm run build
```

Run the backend checks from `backend/` with:

```powershell
python -m unittest discover -s tests -v
```

## Known limitations

- Backend coverage includes TMDB and administration behavior; complete recommendation-ranking coverage remains future work.
- The neural serving checkpoint is currently incompatible with the backend class definition.
- Live metadata depends on TMDB availability. The bundled snapshot and styled poster fallback provide degraded operation.
- The Create React App dependency chain is dated and reports transitive security advisories.
- Production configuration requires explicit secrets, a valid database URL, and a review of data and image licensing.
