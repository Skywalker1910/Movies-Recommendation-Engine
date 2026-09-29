"""
Compare all model versions side by side.

Run after overnight training to decide which models to promote.

  python scripts/compare_all_versions.py
"""
import os
import pathlib
import pickle
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"

ROOT   = pathlib.Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

# Register FunkSVD stub
class FunkSVD:
    def __init__(self, **kw): pass
    def predict(self, u, i): pass
sys.modules['__main__'].FunkSVD = FunkSVD

print("=" * 80)
print("MODEL VERSION COMPARISON")
print("=" * 80)

# ── NeuMF versions ────────────────────────────────────────────────────────────
print("\n--- NeuMF ---")
print(f"{'Version':<25} {'RMSE':>7} {'MAE':>7} {'Params':>10} {'Epochs':>7} {'Dropout':>8}")
print("-" * 75)

# v1 baseline
print(f"{'v1 (original)':25} {'1.0725':>7} {'0.8078':>7} {'26.3M':>10} {'10':>7} {'0.2':>8}")

# v2 (current production)
v2_ncf = MODELS / "ncf_eval_metrics.pkl"
if v2_ncf.exists():
    with open(v2_ncf, "rb") as f:
        ncf_m = pickle.load(f)
    if "ncf_v2" in ncf_m:
        v2 = ncf_m["ncf_v2"]
        cfg = v2.get("config", {})
        print(f"{'v2 (production)':25} {v2['rmse']:>7.4f} {v2['mae']:>7.4f} {'13.1M':>10} "
              f"{v2.get('epochs_trained','?'):>7} {cfg.get('dropout','?'):>8}")

# v3
v3_ncf = MODELS / "v3" / "ncf_eval_metrics.pkl"
if v3_ncf.exists():
    with open(v3_ncf, "rb") as f:
        ncf_m3 = pickle.load(f)
    if "ncf_v3" in ncf_m3:
        v3 = ncf_m3["ncf_v3"]
        cfg = v3.get("config", {})
        params = f"~{sum(cfg.get(k,0) for k in ['gmf_dim','mlp_dim'])/10:.0f}M"
        print(f"{'v3 (candidate)':25} {v3['rmse']:>7.4f} {v3['mae']:>7.4f} {'~18M':>10} "
              f"{v3.get('epochs_trained','?'):>7} {cfg.get('dropout','?'):>8}")
else:
    print(f"{'v3':25} (not yet trained)")


# ── FunkSVD versions ──────────────────────────────────────────────────────────
print(f"\n--- FunkSVD ---")
print(f"{'Version':<25} {'RMSE':>7} {'MAE':>7} {'Factors':>8} {'Epochs':>7} {'NDCG@10':>8} {'Hit@10':>8}")
print("-" * 80)

# v1 (current production)
print(f"{'v1 (production)':25} {'0.7600':>7} {'0.5627':>7} {'50':>8} {'30':>7} {'0.0851':>8} {'0.3970':>8}")

# v2 (rejected)
print(f"{'v2 (rejected)':25} {'0.7638':>7} {'0.5661':>7} {'100':>8} {'55':>7} {'0.0393':>8} {'0.2412':>8}")

# v3
v3_funk = MODELS / "v3" / "funksvd_eval_metrics.pkl"
if v3_funk.exists():
    with open(v3_funk, "rb") as f:
        funk_m3 = pickle.load(f)
    if "funk_v3" in funk_m3:
        v3 = funk_m3["funk_v3"]
        r = v3.get("ranking", {})
        print(f"{'v3 (candidate)':25} {v3['rmse']:>7.4f} {v3['mae']:>7.4f} "
              f"{v3['n_factors']:>8} {v3['epochs']:>7} "
              f"{r.get('NDCG@10','-'):>8} {r.get('Hit@10','-'):>8}")
else:
    print(f"{'v3':25} (not yet trained)")


# ── Hybrid weights ────────────────────────────────────────────────────────────
hybrid_file = MODELS / "hybrid_weight_search.pkl"
if hybrid_file.exists():
    with open(hybrid_file, "rb") as f:
        hw = pickle.load(f)
    best = hw["best"]
    curr = hw["current"]
    print(f"\n--- Hybrid Blend Weights ---")
    print(f"Current:  FunkSVD only       NDCG@10={curr['ndcg10']:.4f}  Hit@10={curr['hit10']:.4f}")
    print(f"Best:     funk={best['w_funk']:.2f} svd2={best['w_svd2']:.2f} pop={best['w_pop']:.2f}  "
          f"NDCG@10={best['ndcg10']:.4f}  Hit@10={best['hit10']:.4f}")
    print(f"Change:   NDCG {best['ndcg10']-curr['ndcg10']:+.4f}  Hit {best['hit10']-curr['hit10']:+.4f}")

print(f"\n{'='*80}")
print("RECOMMENDATION:")

# Decision logic
promote_ncf = False
promote_funk = False

if v3_ncf.exists() and "ncf_v3" in ncf_m3:
    if ncf_m3["ncf_v3"]["rmse"] < 0.8543:
        print("  NeuMF v3: PROMOTE (better than v2)")
        promote_ncf = True
    else:
        print("  NeuMF v3: KEEP v2 (v3 not better)")

if v3_funk.exists() and "funk_v3" in funk_m3:
    v3r = funk_m3["funk_v3"].get("ranking", {})
    if v3r.get("NDCG@10", 0) > 0.0851:
        print("  FunkSVD v3: PROMOTE (better ranking)")
        promote_funk = True
    elif funk_m3["funk_v3"]["rmse"] < 0.7550:
        print("  FunkSVD v3: CONSIDER (better RMSE, check ranking)")
    else:
        print("  FunkSVD v3: KEEP v1 (v3 not better)")

if promote_ncf or promote_funk:
    print(f"\nTo promote winning models:")
    print(f"  python scripts/promote_v2.py  (update for v3 paths)")
else:
    print(f"\nNo models to promote. Current production is optimal.")

print()
