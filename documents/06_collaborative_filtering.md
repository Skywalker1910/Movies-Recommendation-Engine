# Notebook 06: Collaborative Filtering

Notebook: `data_science/notebooks/06_collaborative.ipynb`

## Objective

Establish memory-based user and item collaborative-filtering baselines on the temporal training split.

## Sparse rating matrix

| Property | Value |
|---|---:|
| Users | 226,277 |
| Movies | 24,862 |
| Observed ratings | Approximately 20.7 million |
| Density | 0.37 percent |
| Sparse storage | Approximately 45.3 MB |

A dense representation would require roughly 42 GB, so the implementation uses SciPy CSR matrices and explicit user and movie index maps.

## Methods

User-based CF computes cosine similarity between a target user and all other users. The 50 nearest users contribute similarity-weighted rating predictions.

Item-based CF compares the movies already rated by a user with all candidate movies. The 30 nearest items per rated movie contribute rating-weighted predictions.

The two approaches use MovieLens identifiers internally and `links.csv` to map results back to TMDB metadata.

## Evaluation

The evaluation sampled 200 users with at least 50 training ratings and 5 validation ratings.

| Method | RMSE | MAE | Approximate query latency |
|---|---:|---:|---:|
| User-based CF | 0.9653 | 0.7230 | 332 ms |
| Item-based CF | 0.9647 | 0.7175 | 1,300 ms |

The methods have nearly identical prediction error. Item-based CF is marginally more accurate but substantially slower without precomputed similarities.

## Cold start

Memory-based CF cannot score a user or item that is absent from the matrix. The notebook defines two fallbacks:

- Bayesian-ranked popular movies for new users;
- TF-IDF content similarity for new or unrated items.

## Artifacts

| Artifact | Purpose |
|---|---|
| `user_item_matrix.npz` | User-by-movie CSR matrix |
| `item_user_matrix.npz` | Movie-by-user CSR matrix |
| `user_id_map.pkl` | User index mapping |
| `movie_id_map.pkl` | Movie index mapping |
| `cf_eval_metrics.pkl` | Saved RMSE and MAE values |

## Limitations

- Evaluation favors users with substantial histories.
- Query cost grows with the user or item population.
- The global-mean fallback can hide model coverage failures in aggregate error metrics.
- The experiment does not evaluate diversity or novelty.

The next stage is [matrix factorization](07_matrix_factorization.md).
