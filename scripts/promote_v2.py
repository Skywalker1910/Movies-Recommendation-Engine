"""
Promote v2 model artifacts to production.

After running retrain_neumf.py and retrain_funksvd.py, run this script to:
1. Back up current v1 models to models/v1/
2. Copy v2 artifacts into models/ (production)
3. Print a comparison summary

Run: python scripts/promote_v2.py
Then SCP updated models/ to EC2 and restart the backend.
"""
import pathlib
import pickle
import shutil

ROOT      = pathlib.Path(__file__).resolve().parents[1]
MODELS    = ROOT / "models"
MODELS_V1 = MODELS / "v1"
MODELS_V2 = MODELS / "v2"

if not MODELS_V2.exists():
    print("ERROR: models/v2/ not found. Run retrain scripts first.")
    raise SystemExit(1)

# ── Back up v1 ────────────────────────────────────────────────────────────────
print("Backing up v1 artifacts to models/v1/...")
MODELS_V1.mkdir(exist_ok=True)
v1_files = [
    "funksvd_model.pkl", "funksvd_user_factors.npy", "funksvd_item_factors.npy",
    "ncf_model_weights.pt", "ncf_config.pkl", "ncf_user_enc.pkl",
    "ncf_movie_enc.pkl", "ncf_eval_metrics.pkl",
    "ncf_user_embeddings.npy", "ncf_item_embeddings.npy",
    "mf_eval_metrics.pkl",
]
for name in v1_files:
    src = MODELS / name
    if src.exists():
        shutil.copy2(src, MODELS_V1 / name)
        print(f"  {name} -> v1/")

# ── Promote v2 ────────────────────────────────────────────────────────────────
print("\nPromoting v2 artifacts to production...")
v2_files = list(MODELS_V2.glob("*"))
for src in v2_files:
    if src.is_file() and src.name not in (".", ".."):
        dst = MODELS / src.name
        shutil.copy2(src, dst)
        print(f"  v2/{src.name} -> {src.name}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PROMOTION COMPLETE")
print("=" * 70)

# Load metrics for comparison
v2_ncf_path = MODELS / "ncf_eval_metrics.pkl"
v2_mf_path = MODELS / "mf_eval_metrics.pkl"

if v2_ncf_path.exists():
    with open(v2_ncf_path, "rb") as f:
        ncf_m = pickle.load(f)
    if "ncf_v2" in ncf_m:
        v2 = ncf_m["ncf_v2"]
        print(f"\nNeuMF:  v1 RMSE=1.0725 -> v2 RMSE={v2['rmse']:.4f}  "
              f"(ΔRMSE={1.0725 - v2['rmse']:+.4f})")

if v2_mf_path.exists():
    with open(v2_mf_path, "rb") as f:
        mf_m = pickle.load(f)
    if "funk_v2" in mf_m:
        v2 = mf_m["funk_v2"]
        v2r = v2.get("ranking", {})
        print(f"FunkSVD: v1 RMSE=0.7600 -> v2 RMSE={v2['rmse']:.4f}  "
              f"(ΔRMSE={0.7600 - v2['rmse']:+.4f})")
        print(f"         v1 NDCG@10=0.0851 -> v2 NDCG@10={v2r.get('NDCG@10', '?')}  "
              f"v1 Hit@10=0.3970 -> v2 Hit@10={v2r.get('Hit@10', '?')}")

print(f"\nNext steps:")
print(f"  1. SCP models to EC2:")
print(f"     scp -i <key.pem> -r models/ ec2-user@<IP>:~/Movies-Recommendation-Engine/")
print(f"  2. Restart backend:")
print(f"     docker compose -f docker-compose.prod.yml restart backend")
print(f"  3. (Optional) Keep models/v1/ as rollback")
