# Notebook 01: MovieLens and TMDB Exploration

Notebook: `data_science/notebooks/01_eda_movielens.ipynb`

## Objective

Assess the structure, completeness, and modeling value of the MovieLens ratings and TMDB metadata before defining the preprocessing pipeline.

## Sources

| File | Rows | Role |
|---|---:|---|
| `movies_metadata.csv` | 45,466 | Movie metadata and overviews |
| `credits.csv` | 45,476 | Cast and crew |
| `keywords.csv` | 46,419 | Descriptive tags |
| `ratings_small.csv` | 100,004 | Rapid prototyping |
| `ratings.csv` | 26,024,289 | Full rating history |
| `links.csv` | 45,843 | MovieLens, IMDb, and TMDB identifier bridge |

## Findings

- Three metadata rows contain nonnumeric identifiers and 30 identifiers are duplicated.
- Plot overviews are missing for 2.1 percent of movies; the median available overview is 48 words.
- Cast and director coverage are 94.7 and 98.0 percent respectively.
- About 31.9 percent of movies have no keyword tags.
- The full ratings file contains 270,896 users and 45,115 rated movies.
- Ratings have a mean of 3.528 on a 0.5 to 5.0 scale and are concentrated around 3 and 4 stars.
- The small rating matrix is 98.36 percent sparse, which motivates sparse matrix storage for all collaborative models.
- `links.csv` has complete IMDb identifiers and is missing TMDB identifiers for only 219 rows.

## Decisions

1. Retain non-English movies rather than narrowing the catalog by language.
2. Remove malformed and duplicate movie identifiers.
3. Parse genres, credits, and keywords from their serialized list structures.
4. Build content features from overview, genre, director, cast, and cleaned keywords.
5. Use the full ratings file for final experiments and the small file only for iteration.
6. Use `links.csv` as the authoritative bridge between identifier systems.

## Limitations

The TMDB metadata is an older snapshot. Popularity fields and artwork paths can become stale, and the observed rating distribution reflects self-selection by users rather than random exposure.

## Output

This analysis defines the cleaning rules implemented in [Notebook 04](04_preprocessing.md). The executable analysis and plots remain in the notebook.

