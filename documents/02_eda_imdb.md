# Notebook 02: IMDb Exploration

Notebook: `data_science/notebooks/02_eda_imdb.ipynb`

## Objective

Determine whether the IMDb non-commercial datasets should replace or enrich the MovieLens and TMDB sources.

## Sources

| File | Role |
|---|---|
| `title.basics.tsv` | Titles, years, genres, runtime, and title type |
| `title.ratings.tsv` | Aggregate rating and vote count |
| `title.principals.tsv` | Cast and crew identifiers |
| `name.basics.tsv` | Person-name lookup |

IMDb encodes missing values as the literal string `\N`; loaders convert this value to null.

## Findings

- The inspected title data contains 740,517 entries. Filtering to non-adult movies leaves approximately 280,000 titles.
- IMDb covers a broader historical range than the TMDB snapshot, from 1888 through 2025 in the analyzed files.
- Genre coverage is 89.5 percent.
- Cast and director coverage are 72.2 and 89.3 percent, below the corresponding TMDB coverage.
- IMDb provides aggregate public ratings but no individual user histories.
- IMDb provides no plot overview or keyword fields suitable for the content model.
- Of the MovieLens entries with IMDb identifiers, 39,298 match `title.basics.tsv`; 39,116 are joinable across all three sources.

## Source comparison

| Requirement | MovieLens and TMDB | IMDb |
|---|---|---|
| Individual user ratings | Available | Not available |
| Plot and keyword text | Available | Not available |
| Aggregate rating confidence | Limited | Available |
| Recent catalog coverage | Limited by snapshot | Broader |
| Runtime enrichment | Available with gaps | Available |

## Decision

IMDb is used as an enrichment source rather than the primary catalog. Its aggregate rating and vote-count fields support a confidence-adjusted popularity score, and its runtime can fill selected metadata gaps. Collaborative modeling remains dependent on MovieLens user histories.

The identifier conversion is:

```text
MovieLens imdbId 114709 -> IMDb tconst tt0114709
```

## Limitations

Coverage calculations reflect the local data snapshot and may differ from current IMDb releases. Use of IMDb non-commercial data must remain consistent with its license.

## Output

The filtered enrichment table is constructed in [Notebook 04](04_preprocessing.md) and stored as `imdb_enrichment.parquet`.

