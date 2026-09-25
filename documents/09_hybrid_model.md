# Notebook 09: Hybrid Recommendation

Notebook: `data_science/notebooks/09_hybrid_model.ipynb`

## Objective

Combine rating prediction, content similarity, and popularity so the system can return useful candidates across warm-user and cold-start conditions.

## Signals

| Signal | Source | Function |
|---|---|---|
| FunkSVD | Notebook 07 | Personalized rating estimate |
| NeuMF | Notebook 08 | Nonlinear rating estimate |
| Content similarity | Notebook 05 | Seed-title relevance |
| Bayesian popularity | Notebook 04 | Confidence-aware prior |

Scores are normalized before ranking because the source models operate on different scales.

## Strategies

### Weighted blend

The notebook defines default weights of 0.45 for FunkSVD, 0.30 for NeuMF, 0.15 for popularity, and 0.10 for content similarity. Missing signals are removed and the remaining weights are normalized.

### Switching hybrid

The ranking profile changes with user history:

| History | Primary behavior |
|---|---|
| At least 20 ratings | Collaborative signals dominate |
| 5 to 19 ratings | Balanced collaborative and fallback signals |
| Fewer than 5 ratings | Popularity and content dominate |
| Seed movie supplied | Content weight increases |

### Ridge meta-learner

A Ridge regression model was fit to 5,000 validation pairs using FunkSVD prediction, NeuMF prediction, and Bayesian popularity as features.

## Validation

| Model | RMSE | MAE |
|---|---:|---:|
| Ridge meta-learner | 0.9833 | 0.7533 |
| Weighted rating blend | 1.0064 | 0.7870 |

The learned Ridge coefficients were 0.2803 for FunkSVD, 0.5524 for NeuMF, and 0.1494 for popularity, with an intercept of -0.4711.

These values use a random 5,000-pair validation sample and should not be compared directly with the 200-user model table. Popularity and content are ranking signals, so the weighted RMSE calculation uses rating predictors only.

## Candidate generation

The notebook builds a pool of up to 500 Bayesian-ranked movies, removes movies already seen by the user, and scores only the remaining candidates. This limits online work while maintaining a broad high-confidence pool.

## Artifacts

| Artifact | Purpose |
|---|---|
| `hybrid_meta_learner.pkl` | Fitted Ridge model |
| `hybrid_eval_metrics.pkl` | Weighted and meta-model metrics |
| `hybrid_final_comparison.png` | Experiment comparison figure |

## Application relationship

The Flask service implements a simplified hybrid path using favorite movies, favorite genres, FunkSVD, TF-IDF, and popularity. It does not currently reproduce every notebook strategy exactly, and NeuMF loading is disabled by the checkpoint mismatch described in Notebook 08.

## Limitations

- The hybrid experiment and individual models use different evaluation samples.
- Coverage improves, but diversity, novelty, calibration, and fairness are not measured.
- Candidate generation begins with popularity and can reinforce popularity bias.
- The meta-learner uses a small validation sample and has not been evaluated on the final test partition.

Return to the [documentation index](README.md).
