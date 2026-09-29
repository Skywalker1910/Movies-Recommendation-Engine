# Model Performance Analysis & Retraining Plan

## Current State (after v2 NeuMF fix)

| Model | RMSE | MAE | NDCG@10 | Hit@10 | Status |
|-------|------|-----|---------|--------|--------|
| FunkSVD (50f, 30ep) | **0.7600** | 0.5627 | 0.0851 | 0.3970 | Best RMSE, weak ranking |
| NeuMF v2 (13M params) | 0.8543 | 0.6452 | - | - | Fixed overfitting |
| SVD (user-mean, 100c) | 0.9582 | 0.7109 | **0.1123** | **0.4975** | Best ranking! |
| IBCF | 0.9647 | 0.7175 | - | - | Baseline |
| UBCF | 0.9653 | 0.7230 | - | - | Baseline |
| SVD (global-mean) | 0.9868 | 0.7405 | - | - | Worse than user-mean |
| NMF | 1.0937 | 0.8958 | - | - | Architecturally limited |

## Dataset Characteristics

- 226,499 users x 24,844 movies
- 20.7M ratings (0.37% dense - very sparse)
- **62.8% of users have <50 ratings** - cold/warm start problem
- **12.8% of users have <10 ratings** - true cold start
- Median ratings per user: 28
- Rating scale: 0.5-5.0, global mean: 3.52

## Model-by-Model Diagnosis

### 1. FunkSVD (RMSE 0.76, NDCG 0.085)

**Why RMSE is good**: Biased MF with per-user/item offsets captures rating
scale perfectly. The bu/bi terms handle "harsh raters" vs "generous raters".

**Why ranking is weak**: The MSE loss function optimizes for absolute error
across ALL rating levels. A model that predicts {4.1, 4.0, 3.9} for three
movies has low RMSE but poor ranking if the true order is {3.9, 4.1, 4.0}.
The model doesn't specifically learn to separate "good" from "great".

**Why v2 (100 factors, reg=0.04) failed**: Over-regularization. With reg=0.04
on 100 factors, the larger latent space was suppressed too aggressively.
The model learned less discriminative factors than v1 with reg=0.02.

**Fix strategy**:
- Keep 50 factors (proven) but train MUCH longer (80 epochs + 20 fine-tune)
- Current training RMSE at epoch 30 was 0.6919 - still improving
- With 80+ epochs, training RMSE should reach ~0.65, validation may improve
- The gap was only 0.04 (0.72 train vs 0.76 val) - room to keep training

### 2. NeuMF v2 (RMSE 0.85)

**Why it improved but plateaued at 0.85**:
- Weight decay 5e-3 may be slightly too strong - the model converges fast
  but can't descend further because gradients are dampened
- Dropout 0.4 is aggressive - may be preventing fine-grained learning
- The model stopped at a shallow minimum

**Fix strategy**:
- Try weight_decay=1e-3 (between v1's 1e-4 and v2's 5e-3)
- Try dropout=0.3 (between v1's 0.2 and v2's 0.4)
- Slightly larger architecture: gmf_dim=24, mlp_dim=48, layers=[96, 48]
- Train for 40 epochs with patience=8 (more time to explore)

### 3. SVD User-Mean (RMSE 0.96, NDCG 0.112)

**Why ranking is the BEST despite mediocre RMSE**: User-mean centering
removes scale bias BEFORE decomposition. The latent factors learn
RELATIVE preferences (how much more/less than average a user likes
something), not absolute ratings. This directly optimizes ordering.

**Why RMSE is worse**: Re-adding user_means at prediction time introduces
noise - the mean is estimated from sparse data and noisy for low-activity
users. But for ranking (which ignores scale), this doesn't matter.

**Fix strategy**: Not retrained - already using sklearn TruncatedSVD which
converges in one pass. But we SHOULD integrate it into the hybrid pipeline
as a ranking signal (it's currently unused in production).

### 4. NMF (RMSE 1.09) - SKIP

Non-negativity constraint prevents modeling dislikes. Treats 99.6% sparse
zeros as observed 0-ratings. Fundamentally wrong for this task.
Keep as baseline comparison only.

## Overnight Retraining Plan

### Script 1: FunkSVD v3 (CPU, ~6-8 hours)
- 50 factors, reg=0.02 (proven)
- 80 epochs initial + 20 fine-tune (lr/4) = 100 total epochs
- Expected: RMSE 0.74-0.76, hopefully better ranking from deeper convergence

### Script 2: NeuMF v3 (GPU, ~4-5 hours)
- gmf_dim=24, mlp_dim=48, layers=[96, 48] (~18M params)
- dropout=0.3, weight_decay=1e-3
- 40 epochs, patience=8, batch_size=2048
- Expected: RMSE 0.82-0.85

### Script 3: Hybrid weight optimization (CPU, ~30 min)
- Grid search over blend weights using validation data
- Tests integration of SVD user-mean ranking signal
- Outputs optimal weights for the serving config

## Expected Improvement

After overnight training and weight optimization:
- FunkSVD: RMSE 0.76 -> 0.74-0.75, better convergence
- NeuMF: RMSE 0.85 -> 0.82-0.84, less aggressive regularization
- Hybrid: integrate SVD ranking signal, optimize blend weights
- Overall recommendation quality: measurably better diversity and relevance
