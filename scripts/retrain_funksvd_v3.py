"""
FunkSVD v3 — Extended training (100 epochs total) for deeper convergence.

Diagnosis: v1 (30 epochs) training RMSE was 0.6919 — still improving.
           v2 (100 factors, reg=0.04) over-regularized, NDCG dropped.

Strategy: Keep proven hyperparameters (50 factors, reg=0.02) but train
          3x longer. 80 epochs + 20 fine-tune at lr/4 = 100 total.

Expected: RMSE 0.74-0.76, better ranking from deeper factor convergence.
Runtime: ~6-8 hours on CPU.
"""
import math
import os
import pathlib
import pickle
import time

import numpy as np
import pandas as pd
import scipy.sparse as sp

os.environ["PYTHONIOENCODING"] = "utf-8"

ROOT      = pathlib.Path(__file__).resolve().parents[1]
MODELS    = ROOT / "models"
MODELS_V3 = MODELS / "v3"
PROCESSED = ROOT / "data_science" / "processed"

MODELS_V3.mkdir(exist_ok=True)


class FunkSVD:
    def __init__(self, n_factors=50, n_epochs=80, lr=0.005, reg=0.02, seed=42):
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

        self.history = []
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
            self.history.append(rmse)
            if verbose:
                print(f"  Epoch {epoch+1:>3}/{self.epochs}  RMSE={rmse:.4f}  ({time.time()-t0:.0f}s)")

        return self

    def extend(self, R_csr, n_epochs=20, lr=None, verbose=True):
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
            self.history.append(rmse)
            if verbose:
                print(f"  Epoch {self.epochs + ep + 1:>3}  RMSE={rmse:.4f}  ({time.time()-t0:.0f}s)")

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
movie_id_map = _m["movie2idx"]

n_users, n_movies = user_item.shape
GLOBAL_MEAN = float(user_item.data.mean())
print(f"Matrix: {n_users:,}x{n_movies:,}, {user_item.nnz:,} ratings")

val_ratings = pd.read_parquet(PROCESSED / "ratings_val.parquet",
                              columns=["userId", "movieId", "rating"])
val_lookup = val_ratings.groupby("userId").apply(
    lambda g: dict(zip(g["movieId"], g["rating"])), include_groups=False
).to_dict()

train_counts = np.diff(user_item.indptr)
qual = [
    uid for uid, row in user_id_map.items()
    if train_counts[row] >= 50 and uid in val_lookup and len(val_lookup[uid]) >= 5
]
np.random.seed(42)
np.random.shuffle(qual)
eval_users = qual[:200]
print(f"Eval users: {len(eval_users)}")


def evaluate_funk(model):
    preds = []
    for uid in eval_users:
        row = user_id_map[uid]
        for mid, true_r in val_lookup[uid].items():
            if mid in movie_id_map:
                preds.append((true_r, model.predict(row, movie_id_map[mid])))
            else:
                preds.append((true_r, GLOBAL_MEAN))
    arr = np.array(preds, dtype=np.float32)
    return float(np.sqrt(np.mean((arr[:,0]-arr[:,1])**2))), float(np.mean(np.abs(arr[:,0]-arr[:,1]))), len(preds)


def ranking_at_k(model, k=10, like_threshold=4.0):
    prec_l, recall_l, ndcg_l, hit_l = [], [], [], []
    for uid in eval_users:
        row = user_id_map[uid]
        liked = {movie_id_map[mid] for mid, r in val_lookup[uid].items()
                 if r >= like_threshold and mid in movie_id_map}
        if not liked:
            continue
        scores = model.global_mean + model.bu[row] + model.bi + model.P[row] @ model.Q.T
        scores[user_item[row].indices] = -np.inf
        top = np.argsort(scores)[-k:][::-1]
        hits = sum(1 for c in top if c in liked)
        prec_l.append(hits/k)
        recall_l.append(hits/len(liked))
        hit_l.append(1 if hits > 0 else 0)
        dcg = sum(1/math.log2(r+2) for r, c in enumerate(top) if c in liked)
        idcg = sum(1/math.log2(r+2) for r in range(min(k, len(liked))))
        ndcg_l.append(dcg/idcg if idcg > 0 else 0)
    return {f"P@{k}": round(np.mean(prec_l),4), f"R@{k}": round(np.mean(recall_l),4),
            f"NDCG@{k}": round(np.mean(ndcg_l),4), f"Hit@{k}": round(np.mean(hit_l),4)}


# ── Phase 1: 80 epochs ───────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Phase 1: FunkSVD v3 -- k=50, 80 epochs, lr=0.005, reg=0.02")
print("=" * 70)

t0 = time.time()
funk = FunkSVD(n_factors=50, n_epochs=80, lr=0.005, reg=0.02, seed=42)
funk.fit(user_item, verbose=True)
print(f"\nPhase 1 time: {(time.time()-t0)/60:.1f} min")

rmse_80, mae_80, n = evaluate_funk(funk)
print(f"\nFunkSVD v3 (80 ep) -> RMSE={rmse_80:.4f}  MAE={mae_80:.4f}  ({n:,} preds)")


# ── Phase 2: +20 fine-tune at lr/4 ───────────────────────────────────────────
print("\n" + "=" * 70)
print("Phase 2: Fine-tune +20 epochs, lr=0.00125")
print("=" * 70)

t0 = time.time()
funk.extend(user_item, n_epochs=20, lr=0.00125, verbose=True)
print(f"\nPhase 2 time: {(time.time()-t0)/60:.1f} min")

rmse_ft, mae_ft, n = evaluate_funk(funk)
print(f"\nFunkSVD v3 ({funk.epochs} ep) -> RMSE={rmse_ft:.4f}  MAE={mae_ft:.4f}  ({n:,} preds)")


# ── Ranking ───────────────────────────────────────────────────────────────────
print("\nComputing ranking metrics...")
rank = ranking_at_k(funk, k=10)
for key, val in rank.items():
    print(f"  {key}: {val}")


# ── Comparison ────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)
print(f"{'Model':<35} {'RMSE':>7} {'MAE':>7} {'NDCG@10':>8} {'Hit@10':>8}")
print("-" * 70)
print(f"{'FunkSVD v1 (50f, 30ep)':35} {'0.7600':>7} {'0.5627':>7} {'0.0851':>8} {'0.3970':>8}")
print(f"{'FunkSVD v3 (50f, '+str(funk.epochs)+'ep)':35} {rmse_ft:>7.4f} {mae_ft:>7.4f} {rank['NDCG@10']:>8.4f} {rank['Hit@10']:>8.4f}")
print("=" * 70)


# ── Save ──────────────────────────────────────────────────────────────────────
print("\nSaving v3 artifacts...")

with open(MODELS_V3 / "funksvd_model.pkl", "wb") as f:
    pickle.dump(funk, f)
np.save(MODELS_V3 / "funksvd_user_factors.npy", funk.P.astype(np.float32))
np.save(MODELS_V3 / "funksvd_item_factors.npy", funk.Q.astype(np.float32))

metrics = {
    "funk_v3": {"rmse": rmse_ft, "mae": mae_ft, "epochs": funk.epochs,
                "n_factors": funk.k, "ranking": rank, "history": funk.history},
    "funk_v1": {"rmse": 0.7600, "mae": 0.5627, "epochs": 30, "n_factors": 50,
                "ranking": {"NDCG@10": 0.0851, "Hit@10": 0.3970}},
}
with open(MODELS_V3 / "funksvd_eval_metrics.pkl", "wb") as f:
    pickle.dump(metrics, f)

print("\nArtifacts saved to models/v3/:")
for f in sorted(MODELS_V3.glob("funksvd*")):
    print(f"  {f.name:<40} {f.stat().st_size/1024:.1f} KB")

print("\n[OK] FunkSVD v3 retraining complete!")
