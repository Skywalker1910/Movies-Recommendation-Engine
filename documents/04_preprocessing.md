# Notebook 04: Preprocessing Pipeline

Notebook: `data_science/notebooks/04_preprocessing.ipynb`

## Objective

Implement the source-cleaning, joining, feature-engineering, and temporal-splitting specification from Notebook 03.

## Pipeline

```text
movies_metadata.csv -> movies_clean.parquet
credits.csv         -> credits_clean.parquet
keywords.csv        -> keywords_clean.parquet
IMDb TSV files      -> imdb_enrichment.parquet
clean tables        -> master_movies.parquet
ratings.csv         -> train, validation, and test Parquet files
```

## Cleaning rules

### Movies

- Remove three nonnumeric identifiers and 30 duplicate identifiers.
- Rename the primary key to `tmdb_id`.
- Parse genre lists and derive release year.
- Normalize overview text.
- Standardize rating, vote, runtime, language, and popularity columns.

The cleaned table contains 45,433 movies.

### Credits and keywords

- Select the first credited director.
- Retain the first three cast members by billing order.
- Normalize keyword text.
- Remove known metadata artifacts such as `duringcreditsstinger`, `aftercreditsstinger`, and `woman director`.

### IMDb enrichment

- Restrict `title.basics.tsv` to non-adult movies.
- Join aggregate ratings on `tconst`.
- Restrict the result to MovieLens-linked titles.
- Retain IMDb score, vote count, log vote count, and runtime.

The enrichment table contains 39,176 rows.

## Engineered features

`content_soup` is the combined text used by the content model:

```text
overview + genres + genres + director + director + cast + keywords
```

`bayesian_score` combines rating and vote confidence so that movies with few votes are pulled toward the catalog mean.

## Temporal split

| Artifact | Period | Rows |
|---|---|---:|
| `ratings_train.parquet` | Before 2015 | 20,720,316 |
| `ratings_val.parquet` | 2015 | 1,913,720 |
| `ratings_test.parquet` | 2016 and later | 3,390,253 |

## Outputs

| Artifact | Rows | Purpose |
|---|---:|---|
| `movies_clean.parquet` | 45,433 | Clean movie metadata |
| `credits_clean.parquet` | 45,432 | Director and cast |
| `keywords_clean.parquet` | 45,432 | Keyword lists |
| `imdb_enrichment.parquet` | 39,176 | IMDb enrichment |
| `master_movies.parquet` | 45,433 | Final model feature table |

## Validation

The notebook verifies that:

- `tmdb_id` is unique in the master catalog;
- rating periods do not overlap;
- output row counts match the in-memory tables;
- list-valued features survive Parquet serialization.

PyArrow may return list-valued columns as array objects. Downstream notebooks normalize them after loading:

```python
df[column] = df[column].apply(lambda value: list(value) if value is not None else [])
```

## Limitations

The pipeline is notebook-driven rather than packaged as a versioned command-line workflow. Reproducibility also depends on retaining the same source snapshots.

The next stage is [content-based filtering](05_content_based.md).

