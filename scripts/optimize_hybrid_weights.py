"""
Optimize hybrid blend weights using grid search on validation data.

Currently the serving config uses fixed weights:
  popularityWeight=1.0, funkSvdWeight=0.35, neuMfWeight=0.15

This script evaluates different weight combinations and also tests
integrating SVD user-mean (best ranking model, currently unused).

Run: python scripts/optimize_hybrid_weights.py
Runtime: ~30-60 minutes on CPU
"""
import itertools
import math
import os
import pathlib
import pickle
import sys
import time

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.decomposition import TruncatedSVD

os.environ["PYTHONIOENCODING"] = "utf-8"

ROOT      = pathlib.Path(__file__).resolve().parents[1]
MODELS    = ROOT / "models"
PROCESSED = ROOT / "data_science" / "processed"

# Register FunkSVD stub
class FunkSVD:
    def __init__(self, n_factors=50, n_epochs=20, lr=0.005, reg=0.02, seed=42):
        self.k, self.epochs, self.lr, self.reg, self.seed = n_factors, n_epochs, lr, reg, seed
    def predict(self, u, i):
        return float(np.clip(self.global_mean + self.bu[u] + self.bi[i] + np.dot(self.P[u], self.Q[i]), 0.5, 5.0))
sys.modules['__main__'].FunkSVD = FunkSVD

# ── Load everything ───────────────────────────────────────────────────────────
print("Loading artifacts...")
user_item = sp.load_npz(MODELS / "user_item_matrix.npz")
with open(MODELS / "user_id_map.pkl", "rb") as f:
    _u = pickle.load(f)
with open(MODELS / "movie_id_map.pkl", "rb") as f:
    _m = pickle.load(f)
user_id_map = _u["user2idx"]
movie_id_map = _m["movie2idx"]
idx_to_movie = _m["idx2movie"]

with open(MODELS / "funksvd_model.pkl", "rb") as f:
    funk = pickle.load(f)

# SVD user-mean (best ranking model)
U2 = np.load(MODELS / "svd2_user_factors.npy")
Vt2 = np.load(MODELS / "svd2_item_factors.npy").T  # stored as (n_movies, k), need (k, n_movies)
user_means = np.load(MODELS / "svd2_user_means.npy")

# Bayesian popularity
master = pd.read_parquet(PROCESSED / "master_movies.parquet",
                         columns=["tmdb_id", "title", "bayesian_score"])
bayesian = master.set_index("tmdb_id")["bayesian_score"].to_dict()

links = pd.read_csv(ROOT / "data" / "movielens" / "links.csv", usecols=["movieId", "tmdbId"])
links = links.dropna(subset=["tmdbId"])
links["tmdbId"] = links["tmdbId"].astype(int)
links["movieId"] = links["movieId"].astype(int)
movie2tmdb = links.set_index("movieId")["tmdbId"].to_dict()

n_users, n_movies = user_item.shape
GLOBAL_MEAN = float(user_item.data.mean())

val_ratings = pd.read_parquet(PROCESSED / "ratings_val.parquet",
                              columns=["userId", "movieId", "rating"])
val_lookup = val_ratings.groupby("userId").apply(
    lambda g: dict(zip(g["movieId"], g["rating"])), include_groups=False
).to_dict()

train_counts = np.diff(user_item.indptr)
qual = [uid for uid, row in user_id_map.items()
        if train_counts[row] >= 50 and uid in val_lookup and len(val_lookup[uid]) >= 5]
np.random.seed(42)
np.random.shuffle(qual)
eval_users = qual[:200]

print(f"Loaded: {n_users:,}x{n_movies:,} matrix, {len(eval_users)} eval users")
print(f"FunkSVD: k={funk.k}, epochs={funk.epochs}")
print(f"SVD user-mean: U2={U2.shape}, Vt2={Vt2.shape}")


# ── Scoring functions ─────────────────────────────────────────────────────────
def score_funk(row):
    return funk.global_mean + funk.bu[row] + funk.bi + funk.P[row] @ funk.Q.T

def score_svd2(row):
    return U2[row] @ Vt2 + user_means[row]

def score_pop(movie_cols):
    scores = np.zeros(n_movies)
    for col in range(n_movies):
        mid = idx_to_movie.get(col, -1)
        tmdb = movie2tmdb.get(mid, -1)
        scores[col] = bayesian.get(tmdb, 0)
    return scores

print("Pre-computing popularity scores...")
pop_scores = score_pop(range(n_movies))
pop_min, pop_max = pop_scores.min(), pop_scores.max()
pop_norm = (pop_scores - pop_min) / (pop_max - pop_min + 1e-8)


# ── Ranking evaluation ───────────────────────────────────────────────────────
def evaluate_blend(w_funk, w_svd2, w_pop, k=10, like_threshold=4.0):
    ndcg_l, hit_l = [], []

    for uid in eval_users:
        row = user_id_map[uid]
        liked = {movie_id_map[mid] for mid, r in val_lookup[uid].items()
                 if r >= like_threshold and mid in movie_id_map}
        if not liked:
            continue

        # Blend scores
        s = np.zeros(n_movies)
        if w_funk > 0:
            fs = score_funk(row)
            fs_min, fs_max = fs.min(), fs.max()
            if fs_max > fs_min:
                s += w_funk * (fs - fs_min) / (fs_max - fs_min)

        if w_svd2 > 0:
            ss = score_svd2(row)
            ss_min, ss_max = ss.min(), ss.max()
            if ss_max > ss_min:
                s += w_svd2 * (ss - ss_min) / (ss_max - ss_min)

        if w_pop > 0:
            s += w_pop * pop_norm

        # Exclude seen
        s[user_item[row].indices] = -np.inf

        top = np.argsort(s)[-k:][::-1]
        hits = sum(1 for c in top if c in liked)
        hit_l.append(1 if hits > 0 else 0)
        dcg = sum(1/math.log2(r+2) for r, c in enumerate(top) if c in liked)
        idcg = sum(1/math.log2(r+2) for r in range(min(k, len(liked))))
        ndcg_l.append(dcg/idcg if idcg > 0 else 0)

    return round(np.mean(ndcg_l), 4), round(np.mean(hit_l), 4)


# ── Grid search ───────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("Grid search over hybrid blend weights")
print("=" * 70)

# Test individual models first
print("\nBaseline (individual models):")
for name, w in [("FunkSVD only", (1,0,0)), ("SVD user-mean only", (0,1,0)), ("Popularity only", (0,0,1))]:
    ndcg, hit = evaluate_blend(*w)
    print(f"  {name:<25} NDCG@10={ndcg:.4f}  Hit@10={hit:.4f}")

# Grid search
funk_weights = [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]
svd2_weights = [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]
pop_weights  = [0.0, 0.05, 0.1, 0.15, 0.2]

print(f"\nSearching {len(funk_weights)*len(svd2_weights)*len(pop_weights)} combinations...")
results = []
t0 = time.time()

for w_f, w_s, w_p in itertools.product(funk_weights, svd2_weights, pop_weights):
    if w_f + w_s + w_p == 0:
        continue
    ndcg, hit = evaluate_blend(w_f, w_s, w_p)
    results.append((w_f, w_s, w_p, ndcg, hit))

elapsed = time.time() - t0
print(f"Search complete in {elapsed:.0f}s")

# Sort by NDCG
results.sort(key=lambda x: x[3], reverse=True)

print(f"\nTop 15 configurations by NDCG@10:")
print(f"{'w_funk':>7} {'w_svd2':>7} {'w_pop':>7} {'NDCG@10':>8} {'Hit@10':>8}")
print("-" * 50)
for w_f, w_s, w_p, ndcg, hit in results[:15]:
    print(f"{w_f:>7.2f} {w_s:>7.2f} {w_p:>7.2f} {ndcg:>8.4f} {hit:>8.4f}")

# Best config
best = results[0]
print(f"\n{'='*70}")
print(f"BEST CONFIG: w_funk={best[0]}, w_svd2={best[1]}, w_pop={best[2]}")
print(f"             NDCG@10={best[3]:.4f}  Hit@10={best[4]:.4f}")
print(f"{'='*70}")

# Compare with current
print(f"\nCurrent (FunkSVD only): NDCG@10=0.0851  Hit@10=0.3970")
print(f"Best blend:             NDCG@10={best[3]:.4f}  Hit@10={best[4]:.4f}")
print(f"Improvement:            NDCG +{best[3]-0.0851:.4f}  Hit +{best[4]-0.3970:.4f}")

# Save results
with open(MODELS / "hybrid_weight_search.pkl", "wb") as f:
    pickle.dump({
        "results": results,
        "best": {"w_funk": best[0], "w_svd2": best[1], "w_pop": best[2],
                 "ndcg10": best[3], "hit10": best[4]},
        "current": {"ndcg10": 0.0851, "hit10": 0.3970},
    }, f)

print(f"\nResults saved to models/hybrid_weight_search.pkl")
print(f"\nTo apply the best config in production, update admin model config:")
print(f"  funkSvdWeight = {best[0]}")
print(f"  popularityWeight = {best[2]}")
print(f"  (SVD user-mean integration requires ml_service.py update)")

print("\n[OK] Hybrid weight optimization complete!")
