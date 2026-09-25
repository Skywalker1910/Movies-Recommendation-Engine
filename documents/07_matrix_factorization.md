# Notebook 07: Matrix Factorization

Notebook: `data_science/notebooks/07_matrix_factorization.ipynb`

## Objective

Compare latent-factor approaches for explicit rating prediction and top-10 recommendation quality.

## Methods

| Model | Description |
|---|---|
| Global-mean TruncatedSVD | Low-rank decomposition after centering observed entries on the catalog mean |
| User-mean TruncatedSVD | Low-rank decomposition after centering observed entries by user |
| FunkSVD | Biased matrix factorization optimized on observed ratings with SGD |
| NMF | Nonnegative factorization with a post-fit rating offset |

FunkSVD models a rating as the global mean, user bias, movie bias, and the dot product of user and movie factors. The final run uses 50 latent factors and 30 epochs, with a lower learning rate for epochs 21 through 30.

## Rating-prediction results

The evaluation uses the same 200 qualifying-user protocol as Notebook 06.

| Model | RMSE | MAE |
|---|---:|---:|
| FunkSVD, 30 epochs | 0.7600 | 0.5627 |
| FunkSVD, 20 epochs | 0.7644 | 0.5670 |
| User-mean TruncatedSVD | 0.9582 | 0.7109 |
| Global-mean TruncatedSVD | 0.9868 | 0.7405 |
| Calibrated NMF | 1.0937 | 0.8958 |

Extending FunkSVD reduced training RMSE from 0.7225 to 0.6919 but improved validation RMSE by only 0.0044. This gap suggests diminishing generalization and the onset of overfitting.

## Ranking results

| Model | Precision@10 | Recall@10 | NDCG@10 | Hit Rate@10 |
|---|---:|---:|---:|---:|
| User-mean TruncatedSVD | 0.0945 | 0.0499 | 0.1123 | 0.4975 |
| FunkSVD | 0.0709 | 0.0448 | 0.0851 | 0.3970 |

The central finding is that the model with the lowest rating error does not produce the strongest ranked lists. FunkSVD directly minimizes squared rating error, while the SVD representation produces better top-10 ordering under the selected ranking protocol.

## Implementation findings

### Sparse-matrix centering

Applying TruncatedSVD directly to a matrix in which missing ratings appear as zero produced severely biased predictions. The corrected method subtracts a mean only from observed entries and adds the corresponding mean back during prediction.

### NMF calibration

NMF must use nonnegative input and therefore cannot use mean-centered ratings. With more than 99 percent unobserved entries represented as zero, raw predictions were strongly compressed. A global offset improved its scale but did not make it competitive for explicit rating prediction.

### Computational cost

User-mean TruncatedSVD fit in seconds. The pure-Python FunkSVD loop required approximately 85 minutes for 20 epochs and another 42 minutes for the final 10 epochs. A compiled or vectorized implementation would be necessary for frequent retraining.

## Artifacts

The notebook stores SVD and FunkSVD user and movie factors, the serialized FunkSVD model, mapping tables, evaluation metrics, and comparison figures in `models/`.

## Limitations

- Results are based on power users and may be optimistic for sparse histories.
- Ranking evaluation covers 199 qualifying users, not the full catalog population.
- Hyperparameter exploration is limited rather than exhaustive.
- The pure-Python FunkSVD implementation is useful for study but not efficient for scheduled retraining.

The next stage is [neural collaborative filtering](08_neural_network.md).

