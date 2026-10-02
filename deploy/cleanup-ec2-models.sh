#!/bin/bash
# =============================================================================
# EC2 Model Cleanup — Remove unused ML artifacts
#
# Run on EC2 after deploying the latest code:
#   bash deploy/cleanup-ec2-models.sh
#
# Removes unused model files, downloads NCF v3 from HuggingFace, and frees
# disk space on t3.micro instances.
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
    # Legacy content model from earlier iteration — NOT used by ml_service.py
    "content_model.pkl"        # 15GB
    # Collaborative model pickle — not loaded by current pipeline
    "collaborative_model.pkl"  # 9.2MB
    # Evaluation/research artifacts — not needed at serving time
    "mf_eval_metrics.pkl"
    "hybrid_eval_metrics.pkl"
    "cf_eval_metrics.pkl"
    "nmf_config.pkl"
    "hybrid_meta_learner.pkl"
    "mf_comparison.png"
    "all_methods_comparison.png"
    "hybrid_final_comparison.png"
    "ncf_training_curve.png"
    # NCF embeddings (npy) — only the encoder pickles are used
    "ncf_user_embeddings.npy"
    "ncf_item_embeddings.npy"
    # Item-user matrix (transposed duplicate)
    "item_user_matrix.npz"
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

# Download NCF v3 from HuggingFace (models volume is read-only in Docker)
echo "--- Downloading NCF v3 from HuggingFace to host ---"
NCF_FILES=("ncf_model_weights.pt" "ncf_config.pkl" "ncf_user_enc.pkl" "ncf_movie_enc.pkl")
ncf_missing=0
for f in "${NCF_FILES[@]}"; do
    [ ! -f "${MODELS_DIR}/${f}" ] && ncf_missing=1 && break
done

if [ "$ncf_missing" -eq 1 ]; then
    pip install -q huggingface_hub 2>/dev/null || pip3 install -q huggingface_hub 2>/dev/null || true
    python3 -c "
from huggingface_hub import hf_hub_download
files = ['ncf_model_weights.pt', 'ncf_config.pkl', 'ncf_user_enc.pkl', 'ncf_movie_enc.pkl']
for f in files:
    print(f'  Downloading {f}...')
    hf_hub_download('Skywalker1910/movie-rec-models', f, local_dir='${MODELS_DIR}', repo_type='model')
print('NCF v3 download complete')
" || echo "WARNING: NCF v3 download failed — NeuMF will be unavailable"
else
    echo "NCF v3 files already present, skipping download"
fi

echo ""
echo "Remaining files (used in production):"
ls -lhS "${MODELS_DIR}"/ 2>/dev/null || echo "(none)"
echo ""
echo "Next steps:"
echo "  1. Restart containers: docker compose -f docker-compose.prod.yml up -d --build"
echo "  2. Check logs: docker compose -f docker-compose.prod.yml logs -f backend"
