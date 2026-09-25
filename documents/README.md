# Research Documentation

This directory contains concise records for the nine notebooks in `data_science/notebooks`. Each document states the question, method, evidence, outputs, and limitations of one stage of the project. The notebooks remain the executable source of truth.

## Study sequence

| Notebook | Document | Focus |
|---|---|---|
| `01_eda_movielens.ipynb` | [MovieLens and TMDB exploration](01_eda_movielens.md) | Source quality and rating behavior |
| `02_eda_imdb.ipynb` | [IMDb exploration](02_eda_imdb.md) | Coverage and enrichment value |
| `03_dataset_comparison.ipynb` | [Dataset strategy](03_dataset_comparison.md) | Source selection and join design |
| `04_preprocessing.ipynb` | [Preprocessing](04_preprocessing.md) | Cleaning, features, and temporal split |
| `05_content_based.ipynb` | [Content model](05_content_based.md) | TF-IDF retrieval and proxy evaluation |
| `06_collaborative.ipynb` | [Collaborative filtering](06_collaborative_filtering.md) | User- and item-based baselines |
| `07_matrix_factorization.ipynb` | [Matrix factorization](07_matrix_factorization.md) | SVD, FunkSVD, and NMF |
| `08_neural_network.ipynb` | [Neural collaborative filtering](08_neural_network.md) | NeuMF training and evaluation |
| `09_hybrid_model.ipynb` | [Hybrid model](09_hybrid_model.md) | Coverage-aware model combination |

## Data flow

```text
TMDB metadata -----> cleaned catalog ---------+
TMDB credits ------> director and cast -------|
TMDB keywords -----> cleaned tags ------------+--> master_movies.parquet
IMDb datasets -----> rating enrichment -------|
MovieLens links ---> identifier bridge --------+

MovieLens ratings --> temporal split --> train, validation, and test Parquet files
```

## Processed datasets

| Artifact | Rows | Purpose |
|---|---:|---|
| `master_movies.parquet` | 45,433 | Joined feature catalog |
| `movies_clean.parquet` | 45,433 | Cleaned TMDB metadata |
| `credits_clean.parquet` | 45,432 | Director and cast features |
| `keywords_clean.parquet` | 45,432 | Keyword features |
| `imdb_enrichment.parquet` | 39,176 | IMDb rating and runtime fields |
| `ratings_train.parquet` | 20,720,316 | Ratings before 2015 |
| `ratings_val.parquet` | 1,913,720 | Ratings from 2015 |
| `ratings_test.parquet` | 3,390,253 | Ratings from 2016 onward |

## Evaluation summary

### Content retrieval

| Model | Precision@10 | Protocol |
|---|---:|---|
| TF-IDF cosine | 0.699 | Genre overlap for 100 seed movies |
| TF-IDF with quality reranking | 0.680 | Same proxy protocol |

### Qualifying-user rating prediction

| Model | RMSE | MAE |
|---|---:|---:|
| FunkSVD, 30 epochs | 0.7600 | 0.5627 |
| User-mean TruncatedSVD | 0.9582 | 0.7109 |
| Item-based CF | 0.9647 | 0.7175 |
| User-based CF | 0.9653 | 0.7230 |
| NeuMF | 1.0725 | 0.8078 |
| Calibrated NMF | 1.0937 | 0.8958 |

These values use 200 users with substantial training and validation histories. They are optimistic for cold-start and light users.

### Ranking evaluation

| Model | Precision@10 | Recall@10 | NDCG@10 | Hit Rate@10 |
|---|---:|---:|---:|---:|
| User-mean TruncatedSVD | 0.0945 | 0.0499 | 0.1123 | 0.4975 |
| FunkSVD | 0.0709 | 0.0448 | 0.0851 | 0.3970 |

### Hybrid validation

| Model | RMSE | MAE | Protocol |
|---|---:|---:|---|
| Ridge meta-learner | 0.9833 | 0.7533 | 5,000 validation pairs |
| Weighted blend | 1.0064 | 0.7870 | 5,000 validation pairs |

The hybrid values are not directly comparable with the qualifying-user values because the samples differ.

## Methodological constraints

- Content precision uses genre overlap rather than human relevance judgments.
- Most model comparisons use validation data rather than the final test partition.
- The qualifying-user filter excludes sparse and new users.
- Rating error does not measure diversity, novelty, calibration, or fairness.
- The serving layer currently falls back when the NeuMF checkpoint cannot be loaded.

These constraints are part of the findings and should be retained in any project report or presentation.
