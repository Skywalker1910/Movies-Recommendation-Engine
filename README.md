# Movie Recommendation Engine

A full-stack movie recommendation system powered by a hybrid ML pipeline combining collaborative filtering, neural networks, and content-based similarity. Built with Flask, React, and deployed on AWS EC2.

**Live demo:** [https://movies.adityamore.dev](https://movies.adityamore.dev)

## Overview

This project studies content-based, collaborative, latent-factor, neural, and hybrid approaches to movie recommendation. It includes the full data science workflow, reproducible experiments, serialized model artifacts, a Flask REST API, a React client, and production deployment with CI/CD.

The project originated as the final assignment for **CPSC 8740: AI Receptive Software Engineering** (Fall 2024) and has since been expanded into a comprehensive recommendation study with a production-grade application layer.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, React Router v6, Axios |
| **Backend** | Flask, SQLAlchemy, Flask-JWT-Extended, Flask-Bcrypt |
| **ML Models** | FunkSVD, NeuMF (PyTorch), TF-IDF, Bayesian Popularity |
| **External API** | TMDB (live poster/metadata enrichment) |
| **Database** | SQLite (production), PostgreSQL (Docker dev) |
| **Deployment** | AWS EC2 (t3.micro), Docker, nginx, gunicorn, Let's Encrypt SSL |
| **CI/CD** | GitHub Actions (pytest + jest + Docker build validation + SSH deploy) |

## Features

- **Hybrid recommendations** — blends FunkSVD collaborative filtering, NeuMF neural scoring, TF-IDF content similarity, and Bayesian popularity ranking
- **Personalized onboarding** — users select genres and favorite films during registration to seed recommendations
- **Live TMDB enrichment** — movie posters, metadata, and cast info fetched in real-time with in-memory caching
- **Watch history** — track watched movies and filter them from recommendations
- **Admin dashboard** — isolated admin system with separate credentials for user management, model diagnostics, configuration versioning, and audit logging
- **Lazy ML loading** — model artifacts load on first request to keep cold starts fast

## System Architecture

```text
MovieLens, TMDB, IMDb
          |
          v
9 Jupyter notebooks (EDA, preprocessing, modeling)
          |
          v
Parquet datasets + serialized model artifacts (~200MB)
          |
          v
Flask API (gunicorn) ---- SQLite
          |
          v
nginx (reverse proxy + SSL + static files)
          |
          v
React SPA ---- TMDB API (live enrichment)
```

## Repository Structure

```text
backend/                      Flask API, ML service, and admin system
frontend/                     React 18 client (nginx in production)
data_science/notebooks/       9 analysis and modeling notebooks
deploy/                       EC2 setup script
documents/                    Notebook documentation
.github/workflows/            CI (test + build) and CD (deploy) pipelines
docker-compose.yml            Development environment (PostgreSQL + Flask + React)
docker-compose.prod.yml       Production environment (gunicorn + nginx + SSL)
ARCHITECTURE.md               Detailed API surface and admin documentation
```

## ML Methods

| Method | Primary Signal | Role |
|--------|---------------|------|
| TF-IDF content model | Overview, genres, director, cast, keywords | Similar-title retrieval and cold start |
| User-based CF | Similar users | Memory-based baseline |
| Item-based CF | Similar rating patterns between movies | Memory-based baseline |
| TruncatedSVD | Low-rank user-item representation | Latent-factor baseline |
| FunkSVD | Biased matrix factorization trained by SGD | Explicit-rating prediction |
| NeuMF | Neural user and movie embeddings | Nonlinear interaction model |
| Hybrid model | Collaborative, neural, content, and popularity signals | Coverage-aware ranking |

## Evaluation Highlights

| Model | RMSE | MAE |
|-------|-----:|----:|
| FunkSVD (30 epochs) | 0.7600 | 0.5627 |
| User-mean TruncatedSVD | 0.9582 | 0.7109 |
| Item-based CF | 0.9647 | 0.7175 |
| NeuMF | 1.0725 | 0.8078 |

The hybrid design provides coverage — it falls back to content and popularity signals when a user has insufficient rating history. Evaluated on 200 qualifying users with 50+ training ratings.

## Deployment

The application is deployed on **AWS EC2 t3.micro** (free tier) with automated CI/CD:

```text
Push to main
  -> GitHub Actions: pytest + jest + Docker build validation
  -> All checks pass
  -> Auto-deploy via SSH to EC2
  -> Docker Compose rebuild + cleanup
```

**Infrastructure:**
- EC2 t3.micro with 2GB swap, 30GB EBS
- Elastic IP (52.20.228.248)
- Let's Encrypt SSL (auto-renewing)
- nginx reverse proxy (API + static files)
- Branch protection: PR required, 3 CI checks must pass

## Local Setup

### Requirements

- Python 3.11+
- Node.js 18+

### Backend

```bash
# Create environment
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt

# Configure and run
cp backend/.env.example backend/.env
cd backend
python run.py
```

API runs at `http://localhost:5000`. Health check: `GET /health`.

### Frontend

```bash
cd frontend
npm install
npm start
```

Client runs at `http://localhost:3000`.

### Tests

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend
cd frontend && npm test -- --watchAll=false
```

### Docker (full stack)

```bash
docker compose up --build
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — API surface, admin routes, configuration, TMDB integration
- [documents/](documents/) — notebook-by-notebook methodology and results

## License

This project is for educational and portfolio purposes.

---

Built with Flask, React, scikit-learn, and PyTorch.
