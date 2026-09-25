# Notebook 08: Neural Collaborative Filtering

Notebook: `data_science/notebooks/08_neural_network.ipynb`

## Objective

Evaluate whether a NeuMF architecture improves rating prediction by learning nonlinear interactions between user and movie embeddings.

## Architecture

NeuMF combines two branches:

- generalized matrix factorization with 32-dimensional embeddings;
- a multilayer perceptron with 64-dimensional embeddings and hidden layers of 128, 64, and 32 units.

The concatenated representation passes through a linear output and a scaled sigmoid that restricts predictions to the 0.5 to 5.0 rating range.

| Parameter | Value |
|---|---:|
| Users | 244,905 |
| Movies | 28,733 |
| Approximate parameters | 26.3 million |
| Dropout | 0.2 |
| Optimizer | Adam |
| Learning rate | 0.0005 |
| Batch size | 4,096 |
| Epochs | 10 |

## Training

The final experiment used all 20,720,316 training ratings on a CUDA-capable GPU. A 500,000-row validation sample was evaluated after each epoch. An earlier 2-million-row training sample overfit because most user embeddings received too few observations.

The best sampled validation RMSE was 0.9995 at epoch 8. On the 200 qualifying-user protocol shared with Notebooks 06 and 07, the result was:

| Model | RMSE | MAE |
|---|---:|---:|
| NeuMF | 1.0725 | 0.8078 |
| FunkSVD reference | 0.7600 | 0.5627 |

NeuMF did not outperform the simpler factorization model for established users. The result is useful negative evidence: additional model complexity did not compensate for the sparse, high-cardinality embedding problem under this training design.

## Artifacts

| Artifact | Purpose |
|---|---|
| `ncf_model_weights.pt` | PyTorch state dictionary |
| `ncf_config.pkl` | Architecture parameters |
| `ncf_user_enc.pkl` | User index mapping |
| `ncf_movie_enc.pkl` | Movie index mapping |
| `ncf_user_embeddings.npy` | Exported user embeddings |
| `ncf_item_embeddings.npy` | Exported movie embeddings |
| `ncf_eval_metrics.pkl` | Qualifying-user metrics |
| `ncf_training_curve.png` | Epoch-level training record |

## Serving issue

The checkpoint names layers such as `gmf_user_emb` and `output`, while the current Flask serving class expects names such as `gmf_u` and `out`. PyTorch therefore rejects the state dictionary. The backend catches this error and continues without NeuMF. The class or checkpoint must be migrated before neural inference is considered part of the running application.

## Limitations

- Validation during training used a sample rather than the full validation partition.
- The power-user evaluation does not establish behavior for cold-start users.
- Only one architecture family and a small hyperparameter set were studied.
- The saved model is not currently compatible with the serving class.

The next stage is the [hybrid model](09_hybrid_model.md).

