"""
Retrain FunkSVD with more latent factors and stronger regularization.

Changes from NB07:
  - n_factors:  50 -> 100    (richer latent space for better ranking)
  - n_epochs:   30 -> 40     (extended training with LR decay)
  - reg:        0.02 -> 0.04 (stronger L2 to prevent overfitting with 100 factors)
  - Fine-tune:  +15 epochs at lr/4 for sharper convergence

Expected: RMSE ~0.74-0.76, NDCG@10 improvement from 0.085 -> 0.10+

Run: python scripts/retrain_funksvd.py
Requires: ~3-4 hours on CPU (pure numpy SGD over 20.7M ratings)
"""
import math
import pathlib
import pickle
import time

import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT      = pathlib.Path(__file__).resolve().parents[1]
MODELS    = ROOT / "models"
MODELS_V2 = ROOT / "models" / "v2"
PROCESSED = ROOT / "data_science" / "processed"
MOVIELENS = ROOT / "data" / "movielens"

MODELS_V2.mkdir(exist_ok=True)


# ── FunkSVD class ─────────────────────────────────────────────────────────────
class FunkSVD:
    def __init__(self, n_factors=100, n_epochs=40, lr=0.005, reg=0.04, seed=42):
        self.k = n_factors
        self.epochs = n_epochs
        self.lr = lr
        self.reg = reg
        self.seed = seed

    def fit(self, R_csr, verbose=True):
        rng = np.random.default_rng(self.seed)
        n_u, n_i = R_csr.shape
        self.global_mean = float(R_csr.data.mean())

        scale = 0.1 / np.sqrt(self.k)
        self.P = rng.normal(0, scale, (n_u, self.k)).astype(np.float32)
        self.Q = rng.normal(0, scale, (n_i, self.k)).astype(np.float32)
        self.bu = np.zeros(n_u, dtype=np.float32)
        self.bi = np.zeros(n_i, dtype=np.float32)

        coo = R_csr.tocoo()
        rows, cols, vals = coo.row, coo.col, coo.data.astype(np.float32)
        n_obs = len(vals)
        idx = np.arange(n_obs)

        for epoch in range(self.epochs):
            t0 = time.time()
            rng.shuffle(idx)
            epoch_loss = 0.0

            for k in idx:
                u, i, r = int(rows[k]), int(cols[k]), vals[k]
                pred = (self.global_mean + self.bu[u] + self.bi[i]
                        + np.dot(self.P[u], self.Q[i]))
                e = r - pred
                epoch_loss += e * e

                self.bu[u] += self.lr * (e - self.reg * self.bu[u])
                self.bi[i] += self.lr * (e - self.reg * self.bi[i])
                pu_old = self.P[u].copy()
                self.P[u] += self.lr * (e * self.Q[i] - self.reg * self.P[u])
                self.Q[i] += self.lr * (e * pu_old - self.reg * self.Q[i])

            rmse = np.sqrt(epoch_loss / n_obs)
            if verbose:
                print(f"  Epoch {epoch+1:>2}/{self.epochs}  RMSE={rmse:.4f}  ({time.time()-t0:.0f}s)")

        return self

    def extend(self, R_csr, n_epochs=15, lr=None, verbose=True):
        """Warm-start fine-tuning from current state."""
        lr = lr if lr is not None else self.lr * 0.25
        coo = R_csr.tocoo()
        rows, cols, vals = coo.row, coo.col, coo.data.astype(np.float32)
        n_obs = len(vals)
        idx = np.arange(n_obs)
        rng = np.random.default_rng(self.seed + self.epochs)

        for ep in range(n_epochs):
            t0 = time.time()
            rng.shuffle(idx)
            epoch_loss = 0.0

            for k in idx:
                u, i, r = int(rows[k]), int(cols[k]), vals[k]
                pred = (self.global_mean + self.bu[u] + self.bi[i]
                        + np.dot(self.P[u], self.Q[i]))
                e = r - pred
                epoch_loss += e * e
                self.bu[u] += lr * (e - self.reg * self.bu[u])
                self.bi[i] += lr * (e - self.reg * self.bi[i])
                pu_old = self.P[u].copy()
                self.P[u] += lr * (e * self.Q[i] - self.reg * self.P[u])
                self.Q[i] += lr * (e * pu_old - self.reg * self.Q[i])

            rmse = np.sqrt(epoch_loss / n_obs)
            if verbose:
                print(f"  Epoch {self.epochs + ep + 1:>2}  RMSE={rmse:.4f}  ({time.time()-t0:.0f}s)")

        self.epochs += n_epochs
        return self

    def predict(self, u, i):
        p = float(self.global_mean + self.bu[u] + self.bi[i]
                  + np.dot(self.P[u], self.Q[i]))
        return float(np.clip(p, 0.5, 5.0))


# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading data...")
user_item = sp.load_npz(MODELS / "user_item_matrix.npz")

with open(MODELS / "user_id_map.pkl", "rb") as f:
    _u = pickle.load(f)
with open(MODELS / "movie_id_map.pkl", "rb") as f:
    _m = pickle.load(f)
user_id_map = _u["user2idx"]
idx_to_user = _u["idx2user"]
movie_id_map = _m["movie2idx"]
idx_to_movie = _m["idx2movie"]

n_users, n_movies = user_item.shape
GLOBAL_MEAN = float(user_item.data.mean())
print(f"Matrix: {n_users:,} users x {n_movies:,} movies, {user_item.nnz:,} ratings")
print(f"Global mean: {GLOBAL_MEAN:.4f}")

# Validation data
val_ratings = pd.read_parquet(PROCESSED / "ratings_val.parquet",
                              columns=["userId", "movieId", "rating"])
val_lookup = val_ratings.groupby("userId").apply(
    lambda g: dict(zip(g["movieId"], g["rating"]))
).to_dict()

# Qualifying users
train_counts = np.diff(user_item.indptr)
qual = [
    uid for uid, row in user_id_map.items()
    if train_counts[row] >= 50 and uid in val_lookup and len(val_lookup[uid]) >= 5
]
np.random.seed(42)
np.random.shuffle(qual)
eval_users = qual[:200]
print(f"Eval users: {len(eval_users)}")


# ── Helper functions ──────────────────────────────────────────────────────────
def compute_rmse_mae(predictions):
    arr = np.array(predictions, dtype=np.float32)
    rmse = float(np.sqrt(np.mean((arr[:, 0] - arr[:, 1]) ** 2)))
    mae = float(np.mean(np.abs(arr[:, 0] - arr[:, 1])))
    return rmse, mae


def evaluate_funk(model):
    preds = []
    for uid in eval_users:
        row = user_id_map[uid]
        for mid, true_r in val_lookup[uid].items():
            if mid in movie_id_map:
                col = movie_id_map[mid]
                pred = model.predict(row, col)
            else:
                pred = GLOBAL_MEAN
            preds.append((true_r, pred))
    return compute_rmse_mae(preds), len(preds)


def ranking_at_k(model, k=10, like_threshold=4.0):
    prec_list, recall_list, ndcg_list, hit_list = [], [], [], []

    for uid in eval_users:
        row = user_id_map[uid]
        liked_cols = {
            movie_id_map[mid]
            for mid, r in val_lookup[uid].items()
            if r >= like_threshold and mid in movie_id_map
        }
        if not liked_cols:
            continue

        scores = (model.global_mean + model.bu[row] + model.bi
                  + model.P[row] @ model.Q.T)
        scores[user_item[row].indices] = -np.inf

        top_cols = np.argsort(scores)[-k:][::-1]
        hits_k = sum(1 for c in top_cols if c in liked_cols)

        prec_list.append(hits_k / k)
        recall_list.append(hits_k / len(liked_cols))
        hit_list.append(1 if hits_k > 0 else 0)

        dcg = sum(1 / math.log2(rank + 2) for rank, c in enumerate(top_cols) if c in liked_cols)
        idcg = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(liked_cols))))
        ndcg_list.append(dcg / idcg if idcg > 0 else 0.0)

    return {
        f"P@{k}": round(float(np.mean(prec_list)), 4),
        f"R@{k}": round(float(np.mean(recall_list)), 4),
        f"NDCG@{k}": round(float(np.mean(ndcg_list)), 4),
        f"Hit@{k}": round(float(np.mean(hit_list)), 4),
        "n_users": len(prec_list),
    }


# ── Phase 1: Train FunkSVD v2 (100 factors, 40 epochs) ───────────────────────
print("\n" + "=" * 70)
print("Phase 1: FunkSVD v2 — k=100, 40 epochs, lr=0.005, reg=0.04")
print("=" * 70)

t_start = time.time()
funk = FunkSVD(n_factors=100, n_epochs=40, lr=0.005, reg=0.04, seed=42)
funk.fit(user_item, verbose=True)
print(f"\nPhase 1 time: {(time.time()-t_start)/60:.1f} min")

(rmse_40, mae_40), n_preds = evaluate_funk(funk)
print(f"\nFunkSVD v2 (40 epochs) → RMSE={rmse_40:.4f}  MAE={mae_40:.4f}  ({n_preds:,} preds)")


# ── Phase 2: Fine-tune +15 epochs at lr/4 ────────────────────────────────────
print("\n" + "=" * 70)
print("Phase 2: Fine-tune +15 epochs, lr=0.00125")
print("=" * 70)

t_start = time.time()
funk.extend(user_item, n_epochs=15, lr=0.00125, verbose=True)
print(f"\nPhase 2 time: {(time.time()-t_start)/60:.1f} min")

(rmse_ft, mae_ft), n_preds = evaluate_funk(funk)
print(f"\nFunkSVD v2 ({funk.epochs} epochs) → RMSE={rmse_ft:.4f}  MAE={mae_ft:.4f}  ({n_preds:,} preds)")


# ── Ranking metrics ───────────────────────────────────────────────────────────
print("\nComputing ranking metrics...")
rank = ranking_at_k(funk, k=10)
for key, val in rank.items():
    print(f"  {key}: {val}")


# ── Comparison ────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)
print(f"{'Model':<30} {'RMSE':>7} {'MAE':>7} {'NDCG@10':>8} {'Hit@10':>8}")
print("-" * 70)
print(f"{'FunkSVD v1 (50f, 30ep)':30} {'0.7600':>7} {'0.5627':>7} {'0.0851':>8} {'0.3970':>8}")
print(f"{'FunkSVD v2 (100f, '+str(funk.epochs)+'ep)':30} {rmse_ft:>7.4f} {mae_ft:>7.4f} {rank['NDCG@10']:>8.4f} {rank['Hit@10']:>8.4f}")
print("=" * 70)


# ── Save artifacts ────────────────────────────────────────────────────────────
print("\nSaving v2 artifacts...")

with open(MODELS_V2 / "funksvd_model.pkl", "wb") as f:
    pickle.dump(funk, f)

np.save(MODELS_V2 / "funksvd_user_factors.npy", funk.P.astype(np.float32))
np.save(MODELS_V2 / "funksvd_item_factors.npy", funk.Q.astype(np.float32))

mf_metrics = {
    "funk_v2": {
        "rmse": rmse_ft,
        "mae": mae_ft,
        "epochs": funk.epochs,
        "n_factors": funk.k,
        "ranking": rank,
    },
    "funk_v1": {
        "rmse": 0.7600,
        "mae": 0.5627,
        "epochs": 30,
        "n_factors": 50,
        "ranking": {"NDCG@10": 0.0851, "Hit@10": 0.3970, "P@10": 0.0709},
    },
}
with open(MODELS_V2 / "mf_eval_metrics.pkl", "wb") as f:
    pickle.dump(mf_metrics, f)

print("\nArtifacts saved to models/v2/:")
for f in sorted(MODELS_V2.glob("funksvd_*")):
    print(f"  {f.name:<40} {f.stat().st_size/1024:.1f} KB")

print("\n✓ FunkSVD v2 retraining complete!")
