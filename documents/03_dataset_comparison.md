# Notebook 03: Dataset Strategy

Notebook: `data_science/notebooks/03_dataset_comparison.ipynb`

## Objective

Select a primary data source, define the cross-source join, and specify the preprocessing and validation design used by later experiments.

## Decision

MovieLens and TMDB form the primary dataset. IMDb contributes aggregate rating confidence and selected runtime fields.

The decision follows from the modeling requirements:

- collaborative models require individual MovieLens ratings;
- content models require TMDB overviews and descriptive metadata;
- IMDb aggregate votes improve confidence-aware popularity estimates;
- a rich 45,000-movie catalog is more useful for this study than a larger catalog without user interactions.

## Join design

```text
movies_clean
  |-- left join credits_clean on tmdb_id
  |-- left join keywords_clean on tmdb_id
  |-- left join links.csv on tmdb_id
  `-- left join imdb_enrichment on imdb_tconst
```

Left joins preserve the TMDB catalog when an enrichment record is unavailable.

## Feature specification

The content representation combines:

```text
overview + 2 x genres + 2 x director + top cast + keywords
```

Genre and director tokens are repeated to increase their influence in TF-IDF similarity.

The popularity feature uses a Bayesian weighted score:

```text
score = (v / (v + m)) * R + (m / (v + m)) * C
```

`R` is a movie rating, `v` its vote count, `C` the catalog mean, and `m` the vote threshold. The score reduces the influence of high averages supported by very few votes.

## Temporal evaluation design

| Split | Period | Ratings |
|---|---|---:|
| Training | Before 2015 | 20,720,316 |
| Validation | 2015 | 1,913,720 |
| Test | 2016 and later | 3,390,253 |

A temporal split better represents deployment than a random split because model fitting cannot use ratings recorded after the prediction period.

## Expected outputs

| Artifact | Purpose |
|---|---|
| `movies_clean.parquet` | Clean movie metadata |
| `credits_clean.parquet` | Director and cast features |
| `keywords_clean.parquet` | Clean keyword features |
| `imdb_enrichment.parquet` | IMDb rating and runtime fields |
| `master_movies.parquet` | Joined feature catalog |
| `ratings_train.parquet` | Model fitting |
| `ratings_val.parquet` | Model selection |
| `ratings_test.parquet` | Final evaluation |

## Limitation

The design preserves movies without IMDb matches, but missing enrichment is not random. Less prominent and older movies may have systematically different coverage.

Implementation is documented in [Notebook 04](04_preprocessing.md).
