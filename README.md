# Movie Recommendation Engine

This repository studies content-based, collaborative, latent-factor, neural, and hybrid approaches to movie recommendation. It includes the full data workflow, reproducible experiments, serialized model artifacts, a Flask API, and a React client.

The project began as the final assignment for **CPSC 8740: AI Receptive Software Engineering** in the Fall 2024 semester. The [original course submission](https://github.com/Skywalker1910/Movies-Recommendation-Engine) implemented a smaller Flask application with content-based and collaborative filtering. This repository extends that work into a graduate-level study of data integration, temporal evaluation, cold-start behavior, and model serving.

## Research objectives

The project addresses three questions:

1. How should MovieLens, TMDB, and IMDb data be combined without losing user-level rating information?
2. How do memory-based, matrix-factorization, and neural recommenders compare under a temporal validation design?
3. Can a hybrid system improve coverage while retaining useful personalization for established users?

## Methods

| Method | Primary signal | Role |
|---|---|---|
| TF-IDF content model | Overview, genres, director, cast, keywords | Similar-title retrieval and cold start |
| User-based CF | Similar users | Memory-based baseline |
| Item-based CF | Similar rating patterns between movies | Memory-based baseline |
| TruncatedSVD | Low-rank user-item representation | Latent-factor baseline |
| FunkSVD | Biased matrix factorization trained by SGD | Explicit-rating prediction |
| NeuMF | Neural user and movie embeddings | Nonlinear interaction model |
| Hybrid model | Collaborative, neural, content, and popularity signals | Coverage-aware ranking |

## Data design

MovieLens and TMDB provide the primary catalog and user ratings. IMDb is used only for enrichment because its public datasets contain aggregate ratings rather than individual user histories.

| Dataset | Use in this project |
|---|---|
| MovieLens ratings | Collaborative and latent-factor training |
| TMDB metadata | Titles, overviews, genres, cast, crew, keywords, artwork paths |
| IMDb non-commercial datasets | Rating confidence and runtime enrichment |

The preprocessing pipeline produces a 45,433-movie catalog and uses a temporal split:

| Split | Period | Ratings |
|---|---|---:|
| Training | Before 2015 | 20,720,316 |
| Validation | 2015 | 1,913,720 |
| Test | 2016 and later | 3,390,253 |

## Evaluation summary

The following values come from the saved experiment artifacts. Results should be interpreted within their stated evaluation protocol.

### Content retrieval

The content model was evaluated on 100 seed movies using genre overlap as a proxy for relevance.

| Configuration | Precision@10 | Approximate query latency |
|---|---:|---:|
| TF-IDF cosine similarity | 0.699 | 35 ms |
| TF-IDF with quality reranking | 0.680 | 45 ms |

Genre overlap is a limited proxy and should not be interpreted as a user-study result.

### Rating prediction for qualifying users

These models were evaluated on 200 users with at least 50 training ratings and 5 validation ratings.

| Model | RMSE | MAE |
|---|---:|---:|
| FunkSVD, 30 epochs | 0.7600 | 0.5627 |
| User-mean TruncatedSVD | 0.9582 | 0.7109 |
| Item-based CF | 0.9647 | 0.7175 |
| User-based CF | 0.9653 | 0.7230 |
| NeuMF | 1.0725 | 0.8078 |
| Calibrated NMF | 1.0937 | 0.8958 |

FunkSVD produced the lowest rating error. User-mean SVD produced stronger top-10 ranking metrics than FunkSVD despite its higher RMSE, which demonstrates that rating prediction and ranking quality are not equivalent objectives.

| Model | NDCG@10 | Hit Rate@10 |
|---|---:|---:|
| User-mean TruncatedSVD | 0.1123 | 0.4975 |
| FunkSVD | 0.0851 | 0.3970 |

### Hybrid validation

The hybrid regressors were evaluated on a separate 5,000-pair validation sample and are therefore not directly comparable with the qualifying-user table.

| Model | RMSE | MAE |
|---|---:|---:|
| Ridge meta-learner | 0.9833 | 0.7533 |
| Weighted blend | 1.0064 | 0.7870 |

The main benefit of the hybrid design is coverage: it can fall back to content and popularity signals when a user has insufficient rating history.

## System architecture

```text
MovieLens, TMDB, IMDb
          |
          v
Exploration and preprocessing notebooks
          |
          v
Parquet datasets and serialized model artifacts
          |
          v
Flask API ---- SQLite or PostgreSQL
          |
          v
React client
```

The application also includes an isolated administration console at `/admin`. It uses separate credentials and tokens for account management, service health, TMDB diagnostics, model inventory, MovieLens similarity inspection, versioned recommendation controls, and audit records.

## Repository structure

```text
data/                         Raw MovieLens, TMDB, and IMDb files
data_science/notebooks/       Nine analysis and modeling notebooks
data_science/processed/       Cleaned Parquet datasets
documents/                    Concise notebook and experiment notes
models/                       Trained model artifacts and evaluation outputs
movie_recommendation_system/  Flask backend, React frontend, and Docker setup
requirements.txt              Shared Python dependencies
```

## Local setup

### Requirements

- Python 3.11 or later
- Node.js 18 or later
- A single repository-local Python environment

### Python environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Linux or macOS, activate the environment with `source .venv/bin/activate`.

### Backend

```powershell
Copy-Item movie_recommendation_system\backend\.env.example `
  movie_recommendation_system\backend\.env
Set-Location movie_recommendation_system\backend
python run.py
```

The API runs at `http://localhost:5000`. Its health endpoint is `GET /health`.

### Frontend

In a second terminal:

```powershell
Set-Location movie_recommendation_system\frontend
npm install
npm start
```

The client runs at `http://localhost:3000`.

### Tests

```powershell
Set-Location movie_recommendation_system\frontend
$env:CI='true'
npm test -- --watchAll=false
npm run build
```

## Current limitations

- Most model metrics use the validation set and a power-user sample; a final unbiased test-set study remains future work.
- The neural checkpoint and the backend NeuMF class currently use different parameter names, so the deployed service falls back to FunkSVD, content similarity, and popularity.
- The Flask service enriches catalog results with current TMDB metadata when a backend API key is configured. The bundled snapshot and local poster fallback remain available when TMDB cannot be reached.
- Automated coverage is currently limited to frontend component tests and API smoke checks.
- The repository contains large raw datasets and model artifacts that are not suitable for a typical source-only clone.

## Documentation

The [documentation index](documents/README.md) links each notebook to a concise account of its method, evidence, outputs, and limitations. Application-specific setup and API details are in [movie_recommendation_system/README.md](movie_recommendation_system/README.md).

## Project history

- Fall 2024 course project: [Movies-Recommendation-Engine](https://github.com/Skywalker1910/Movies-Recommendation-Engine)
- Current repository: expanded data pipeline, additional model families, temporal evaluation, hybrid serving, and a React interface
- Documentation style reference: [BB-8](https://github.com/Skywalker1910/BB-8)
