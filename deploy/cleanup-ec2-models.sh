#!/bin/bash
# =============================================================================
# EC2 Model Cleanup — Remove unused ML artifacts
#
# Run on EC2 after deploying the latest code:
#   bash deploy/cleanup-ec2-models.sh
#
# Removes ~340MB of unused model files and forces re-download of NCF v3
# from HuggingFace on next container restart.
# =============================================================================
set -euo pipefail

MODELS_DIR="${HOME}/Movies-Recommendation-Engine/models"

echo "=== EC2 Model Cleanup ==="
echo "Models directory: ${MODELS_DIR}"
echo ""

# Files NOT used by ml_service.py (safe to delete)
UNUSED_FILES=(
    # NMF model — never loaded in production
    "nmf_user_factors.npy"     # 87MB
    "nmf_item_factors.npy"     # 9.5MB
    # SVD v1 — replaced by FunkSVD
    "svd_user_factors.npy"     # 87MB
    "svd_item_factors.npy"     # 9.5MB
    # SVD2 — not yet integrated into production pipeline
    "svd2_user_factors.npy"    # 87MB
    "svd2_item_factors.npy"    # 9.5MB
    "svd2_user_means.npy"      # 885KB
    # FunkSVD raw factors — model uses the pickle, not the npy splits
    "funksvd_user_factors.npy" # 44MB
    "funksvd_item_factors.npy" # 4.8MB
    # Inference-time unused
    "tfidf_vectorizer.joblib"  # 1.2MB (vectorizer not used at serving time)
    "hybrid_weight_search.pkl" # 17KB (research artifact)
    "ncf_eval_metrics.pkl"     # 1.2KB (metrics only)
)

# NCF v2 files to delete so v3 gets downloaded from HuggingFace
NCF_V2_FILES=(
    "ncf_model_weights.pt"
    "ncf_config.pkl"
    "ncf_user_enc.pkl"
    "ncf_movie_enc.pkl"
)

# Also remove the broken title_to_idx.pkl (will be rebuilt in memory)
BROKEN_FILES=(
    "title_to_idx.pkl"
)

freed=0

echo "--- Removing unused model files ---"
for f in "${UNUSED_FILES[@]}"; do
    path="${MODELS_DIR}/${f}"
    if [ -f "$path" ]; then
        size=$(stat -c%s "$path" 2>/dev/null || stat -f%z "$path" 2>/dev/null || echo 0)
        freed=$((freed + size))
        rm -v "$path"
    fi
done

echo ""
echo "--- Removing NCF v2 files (v3 will be downloaded from HuggingFace) ---"
for f in "${NCF_V2_FILES[@]}"; do
    path="${MODELS_DIR}/${f}"
    if [ -f "$path" ]; then
        size=$(stat -c%s "$path" 2>/dev/null || stat -f%z "$path" 2>/dev/null || echo 0)
        freed=$((freed + size))
        rm -v "$path"
    fi
done

echo ""
echo "--- Removing broken pickle (will be rebuilt in memory on load) ---"
for f in "${BROKEN_FILES[@]}"; do
    path="${MODELS_DIR}/${f}"
    if [ -f "$path" ]; then
        size=$(stat -c%s "$path" 2>/dev/null || stat -f%z "$path" 2>/dev/null || echo 0)
        freed=$((freed + size))
        rm -v "$path"
    fi
done

echo ""
freed_mb=$((freed / 1024 / 1024))
echo "=== Cleanup complete: ~${freed_mb}MB freed ==="
echo ""
echo "Remaining files (used in production):"
ls -lhS "${MODELS_DIR}"/ 2>/dev/null || echo "(none)"
echo ""
echo "Next steps:"
echo "  1. Restart containers: docker compose -f docker-compose.prod.yml up -d --build"
echo "  2. NCF v3 will auto-download from HuggingFace on first request"
echo "  3. Check logs: docker compose -f docker-compose.prod.yml logs -f backend"
