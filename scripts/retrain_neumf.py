"""
Retrain NeuMF with smaller architecture and stronger regularization.

Changes from NB08:
  - gmf_dim:      32 -> 16     (halved embedding capacity)
  - mlp_dim:      64 -> 32     (halved embedding capacity)
  - mlp_layers:   [128,64,32] -> [64,32]  (shallower tower)
  - dropout:      0.2 -> 0.4   (2x stronger)
  - weight_decay: 1e-4 -> 5e-3 (50x stronger L2)
  - batch_size:   4096 -> 2048  (noisier gradients)
  - epochs:       10 -> 30 with early stopping (patience=5)
  - Parameters:   26.3M -> ~8M  (70% reduction)

Expected: val RMSE from 1.07 -> 0.85-0.92

Run: python scripts/retrain_neumf.py
Requires: PyTorch with CUDA, ~2-3 hours on RTX 4070
"""
import pathlib
import pickle
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = pathlib.Path(__file__).resolve().parents[1]
MODELS    = ROOT / "models"
MODELS_V2 = ROOT / "models" / "v2"
PROCESSED = ROOT / "data_science" / "processed"

MODELS_V2.mkdir(exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")
if DEVICE.type == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")


# ── Data ──────────────────────────────────────────────────────────────────────
print("\nLoading data...")
train_df = pd.read_parquet(PROCESSED / "ratings_train.parquet",
                           columns=["userId", "movieId", "rating"])
val_df = pd.read_parquet(PROCESSED / "ratings_val.parquet",
                         columns=["userId", "movieId", "rating"])

# Val sample for fast per-epoch eval
VAL_SAMPLE = 500_000
rng = np.random.default_rng(42)
val_idx = rng.choice(len(val_df), size=min(VAL_SAMPLE, len(val_df)), replace=False)
val_df = val_df.iloc[val_idx].reset_index(drop=True)

# Encode IDs
all_users = pd.concat([train_df["userId"], val_df["userId"]]).unique()
all_movies = pd.concat([train_df["movieId"], val_df["movieId"]]).unique()
user_enc = {uid: i for i, uid in enumerate(all_users)}
movie_enc = {mid: i for i, mid in enumerate(all_movies)}

train_df["user_idx"] = train_df["userId"].map(user_enc)
train_df["movie_idx"] = train_df["movieId"].map(movie_enc)
val_df["user_idx"] = val_df["userId"].map(user_enc).fillna(-1).astype(int)
val_df["movie_idx"] = val_df["movieId"].map(movie_enc).fillna(-1).astype(int)
val_df = val_df[(val_df["user_idx"] >= 0) & (val_df["movie_idx"] >= 0)]

N_USERS = len(user_enc)
N_MOVIES = len(movie_enc)
GLOBAL_MEAN = float(train_df["rating"].mean())

print(f"Train: {len(train_df):,} ratings")
print(f"Val:   {len(val_df):,} ratings")
print(f"Users: {N_USERS:,}  Movies: {N_MOVIES:,}")
print(f"Global mean: {GLOBAL_MEAN:.4f}")


# ── Dataset ───────────────────────────────────────────────────────────────────
class RatingsDataset(Dataset):
    def __init__(self, df):
        self.users = torch.tensor(df["user_idx"].values, dtype=torch.long)
        self.movies = torch.tensor(df["movie_idx"].values, dtype=torch.long)
        self.ratings = torch.tensor(df["rating"].values, dtype=torch.float32)

    def __len__(self):
        return len(self.ratings)

    def __getitem__(self, idx):
        return self.users[idx], self.movies[idx], self.ratings[idx]


BATCH_SIZE = 2048
train_loader = DataLoader(RatingsDataset(train_df), batch_size=BATCH_SIZE,
                          shuffle=True, num_workers=0, pin_memory=True)
val_loader = DataLoader(RatingsDataset(val_df), batch_size=BATCH_SIZE,
                        shuffle=False, num_workers=0, pin_memory=True)
print(f"Train batches: {len(train_loader):,}  Val batches: {len(val_loader):,}")


# ── Model (smaller architecture) ─────────────────────────────────────────────
class NeuMF(nn.Module):
    def __init__(self, n_users, n_movies, gmf_dim=16, mlp_dim=32,
                 mlp_layers=(64, 32), dropout=0.4):
        super().__init__()
        self.gmf_user_emb = nn.Embedding(n_users, gmf_dim)
        self.gmf_item_emb = nn.Embedding(n_movies, gmf_dim)
        self.mlp_user_emb = nn.Embedding(n_users, mlp_dim)
        self.mlp_item_emb = nn.Embedding(n_movies, mlp_dim)

        mlp_in = mlp_dim * 2
        layers = []
        for out in mlp_layers:
            layers += [nn.Linear(mlp_in, out), nn.ReLU(), nn.Dropout(dropout)]
            mlp_in = out
        self.mlp_tower = nn.Sequential(*layers)
        self.output = nn.Linear(gmf_dim + mlp_layers[-1], 1)

        nn.init.normal_(self.gmf_user_emb.weight, std=0.01)
        nn.init.normal_(self.gmf_item_emb.weight, std=0.01)
        nn.init.normal_(self.mlp_user_emb.weight, std=0.01)
        nn.init.normal_(self.mlp_item_emb.weight, std=0.01)

    def forward(self, user_ids, item_ids):
        g = self.gmf_user_emb(user_ids) * self.gmf_item_emb(item_ids)
        m = self.mlp_tower(torch.cat([
            self.mlp_user_emb(user_ids), self.mlp_item_emb(item_ids)
        ], 1))
        return 0.5 + 4.5 * torch.sigmoid(self.output(torch.cat([g, m], 1))).squeeze(1)


NCF_CONFIG = {
    "n_users": N_USERS,
    "n_movies": N_MOVIES,
    "gmf_dim": 16,
    "mlp_dim": 32,
    "mlp_layers": [64, 32],
    "dropout": 0.4,
}

model = NeuMF(**NCF_CONFIG).to(DEVICE)
total_params = sum(p.numel() for p in model.parameters())
print(f"\nNeuMF v2 — Parameters: {total_params:,}")
print(model)


# ── Training ──────────────────────────────────────────────────────────────────
def evaluate(model, loader):
    model.eval()
    se, ae, n = 0.0, 0.0, 0
    with torch.no_grad():
        for users, items, ratings in loader:
            users, items, ratings = users.to(DEVICE), items.to(DEVICE), ratings.to(DEVICE)
            preds = model(users, items)
            se += ((preds - ratings) ** 2).sum().item()
            ae += (preds - ratings).abs().sum().item()
            n += len(ratings)
    return (se / n) ** 0.5, ae / n


N_EPOCHS = 30
PATIENCE = 5
LR = 5e-4
WEIGHT_DECAY = 5e-3

optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
criterion = nn.MSELoss()
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode="min", factor=0.5, patience=3
)

best_val_rmse = float("inf")
best_state = None
patience_counter = 0
history = {"train_rmse": [], "val_rmse": [], "train_mae": [], "val_mae": []}

print(f"\nTraining NeuMF v2 — {N_EPOCHS} epochs max, early stopping patience={PATIENCE}")
print(f"LR={LR}, weight_decay={WEIGHT_DECAY}, batch_size={BATCH_SIZE}")
print("=" * 80)

for epoch in range(1, N_EPOCHS + 1):
    model.train()
    epoch_se, epoch_ae, epoch_n = 0.0, 0.0, 0
    t0 = time.time()

    for users, items, ratings in train_loader:
        users, items, ratings = users.to(DEVICE), items.to(DEVICE), ratings.to(DEVICE)
        optimizer.zero_grad()
        preds = model(users, items)
        loss = criterion(preds, ratings)
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            epoch_se += ((preds - ratings) ** 2).sum().item()
            epoch_ae += (preds - ratings).abs().sum().item()
            epoch_n += len(ratings)

    train_rmse = (epoch_se / epoch_n) ** 0.5
    train_mae = epoch_ae / epoch_n
    val_rmse, val_mae = evaluate(model, val_loader)
    scheduler.step(val_rmse)

    history["train_rmse"].append(train_rmse)
    history["val_rmse"].append(val_rmse)
    history["train_mae"].append(train_mae)
    history["val_mae"].append(val_mae)

    improved = val_rmse < best_val_rmse
    if improved:
        best_val_rmse = val_rmse
        best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        patience_counter = 0
    else:
        patience_counter += 1

    cur_lr = optimizer.param_groups[0]["lr"]
    marker = " *" if improved else ""
    print(
        f"Epoch {epoch:>2}/{N_EPOCHS}  "
        f"train RMSE={train_rmse:.4f} MAE={train_mae:.4f}  "
        f"val RMSE={val_rmse:.4f} MAE={val_mae:.4f}  "
        f"lr={cur_lr:.1e}  ({time.time()-t0:.0f}s){marker}"
    )

    if patience_counter >= PATIENCE:
        print(f"\nEarly stopping at epoch {epoch} (no improvement for {PATIENCE} epochs)")
        break

model.load_state_dict(best_state)
print(f"\nBest val RMSE: {best_val_rmse:.4f}")


# ── Evaluation on qualifying users ───────────────────────────────────────────
print("\nEvaluating on 200 qualifying users...")
import scipy.sparse as sp

user_item = sp.load_npz(MODELS / "user_item_matrix.npz")
with open(MODELS / "user_id_map.pkl", "rb") as f:
    _u = pickle.load(f)
with open(MODELS / "movie_id_map.pkl", "rb") as f:
    _m = pickle.load(f)
user_id_map = _u["user2idx"]
movie_id_map = _m["movie2idx"]

val_full = pd.read_parquet(PROCESSED / "ratings_val.parquet",
                           columns=["userId", "movieId", "rating"])
val_lookup = val_full.groupby("userId").apply(
    lambda g: dict(zip(g["movieId"], g["rating"]))
).to_dict()

MIN_TRAIN = 50
MIN_VAL = 5
train_counts = np.diff(user_item.indptr)
qual = [
    uid for uid, row in user_id_map.items()
    if train_counts[row] >= MIN_TRAIN and uid in val_lookup
    and len(val_lookup[uid]) >= MIN_VAL
]
np.random.seed(42)
np.random.shuffle(qual)
eval_users = qual[:200]

model.eval()
preds_list = []
with torch.no_grad():
    for uid in eval_users:
        if uid not in user_enc:
            continue
        u_idx = user_enc[uid]
        for mid, true_r in val_lookup[uid].items():
            if mid in movie_enc:
                m_idx = movie_enc[mid]
                u_t = torch.tensor([u_idx], dtype=torch.long, device=DEVICE)
                m_t = torch.tensor([m_idx], dtype=torch.long, device=DEVICE)
                pred = float(model(u_t, m_t).item())
            else:
                pred = GLOBAL_MEAN
            preds_list.append((true_r, pred))

arr = np.array(preds_list)
final_rmse = float(np.sqrt(np.mean((arr[:, 0] - arr[:, 1]) ** 2)))
final_mae = float(np.mean(np.abs(arr[:, 0] - arr[:, 1])))
print(f"NeuMF v2 → RMSE={final_rmse:.4f}  MAE={final_mae:.4f}  ({len(preds_list):,} predictions)")

# Compare with original
print(f"\nOriginal NeuMF:  RMSE=1.0725  MAE=0.8078")
print(f"NeuMF v2:        RMSE={final_rmse:.4f}  MAE={final_mae:.4f}")
print(f"Improvement:     ΔRMSE={1.0725 - final_rmse:+.4f}")


# ── Save artifacts ────────────────────────────────────────────────────────────
print("\nSaving v2 artifacts...")

torch.save(model.state_dict(), MODELS_V2 / "ncf_model_weights.pt")

with open(MODELS_V2 / "ncf_user_enc.pkl", "wb") as f:
    pickle.dump(user_enc, f)
with open(MODELS_V2 / "ncf_movie_enc.pkl", "wb") as f:
    pickle.dump(movie_enc, f)
with open(MODELS_V2 / "ncf_config.pkl", "wb") as f:
    pickle.dump(NCF_CONFIG, f)

ncf_metrics = {
    "ncf_v2": {
        "rmse": final_rmse,
        "mae": final_mae,
        "best_val_rmse": best_val_rmse,
        "epochs_trained": len(history["train_rmse"]),
        "config": NCF_CONFIG,
    },
    "ncf_v1": {"rmse": 1.0725, "mae": 0.8078},
    "history": history,
}
with open(MODELS_V2 / "ncf_eval_metrics.pkl", "wb") as f:
    pickle.dump(ncf_metrics, f)

# Save embeddings for hybrid
with torch.no_grad():
    gmf_dim = NCF_CONFIG["gmf_dim"]
    u_emb = (model.gmf_user_emb.weight.cpu().numpy() +
             model.mlp_user_emb.weight.cpu().numpy()[:, :gmf_dim]) / 2
    i_emb = (model.gmf_item_emb.weight.cpu().numpy() +
             model.mlp_item_emb.weight.cpu().numpy()[:, :gmf_dim]) / 2
np.save(MODELS_V2 / "ncf_user_embeddings.npy", u_emb.astype(np.float32))
np.save(MODELS_V2 / "ncf_item_embeddings.npy", i_emb.astype(np.float32))

print("\nArtifacts saved to models/v2/:")
for f in sorted(MODELS_V2.glob("ncf_*")):
    print(f"  {f.name:<35} {f.stat().st_size/1024:.1f} KB")

print("\n✓ NeuMF v2 retraining complete!")
