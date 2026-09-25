# Notebook 05: Content-Based Filtering

Notebook: `data_science/notebooks/05_content_based.ipynb`

## Objective

Retrieve movies similar to a seed title without requiring user history. This model also provides a cold-start path for the hybrid system.

## Representation

The model fits TF-IDF to the `content_soup` field from the master catalog.

| Parameter | Value |
|---|---|
| N-grams | Unigrams and bigrams |
| Maximum features | 30,000 |
| Minimum document frequency | 2 |
| Term frequency | Sublinear |
| Stop words | English |

The resulting sparse matrix has shape 45,433 by 30,000. Similarity is computed on demand with cosine similarity instead of materializing a full pairwise matrix.

## Ranking

The default retrieval score is cosine similarity. An optional quality-aware variant reranks a larger candidate set with:

```text
final_score = 0.70 * similarity + 0.30 * normalized_bayesian_score
```

This tradeoff favors recognizable, well-supported movies but slightly reduces the genre-overlap metric.

## Evaluation

One hundred seed movies were evaluated. A recommendation counts as relevant when it shares a genre with its seed.

| Configuration | Precision@5 | Precision@10 | Precision@20 |
|---|---:|---:|---:|
| Cosine similarity | 0.717 | 0.699 | Not recorded |
| Quality reranking | 0.702 | 0.680 | 0.660 |

The selected hyperparameter sweep produced:

| Configuration | Precision@10 |
|---|---:|
| Unigrams | 0.676 |
| Unigrams and bigrams | 0.699 |
| Bigrams without sublinear TF | 0.681 |
| 50,000-feature vocabulary | 0.697 |
| Up to trigrams | 0.691 |

Typical query latency was 31 to 46 milliseconds in the notebook environment.

## Artifacts

| Artifact | Purpose |
|---|---|
| `tfidf_vectorizer.joblib` | Fitted text transformation |
| `tfidf_matrix.npz` | Sparse movie vectors |
| `title_to_idx.pkl` | Title-to-row mapping |

## Interpretation and limitations

Genre overlap is a convenient proxy, not a direct measure of user satisfaction. It rewards thematic consistency and does not measure novelty or serendipity. Duplicate titles also require a more stable identifier-based lookup in future work.

The next stage is [collaborative filtering](06_collaborative_filtering.md).

