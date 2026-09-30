"""
Upload production models to Hugging Face Hub.

First-time setup:
  pip install huggingface_hub
  huggingface-cli login

Usage:
  python scripts/upload_models_hf.py                    # upload production models
  python scripts/upload_models_hf.py --include-training  # also upload training artifacts
  python scripts/upload_models_hf.py --tag v2-models     # tag current commit on HF
"""
import argparse
import os
import pathlib
import shutil
import tempfile

from huggingface_hub import HfApi, create_repo

REPO_ID = "Skywalker1910/movie-rec-models"
ROOT = pathlib.Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

PRODUCTION_FILES = [
    "funksvd_model.pkl",
    "user_item_matrix.npz",
    "user_id_map.pkl",
    "movie_id_map.pkl",
    "ncf_model_weights.pt",
    "ncf_config.pkl",
    "ncf_user_enc.pkl",
    "ncf_movie_enc.pkl",
    "tfidf_matrix.npz",
    "title_to_idx.pkl",
]

TRAINING_FILES = [
    "svd_user_factors.npy",
    "svd_item_factors.npy",
    "svd2_user_factors.npy",
    "svd2_item_factors.npy",
    "svd2_user_means.npy",
    "nmf_user_factors.npy",
    "nmf_item_factors.npy",
    "tfidf_vectorizer.joblib",
    "ncf_eval_metrics.pkl",
]


def main():
    parser = argparse.ArgumentParser(description="Upload models to Hugging Face Hub")
    parser.add_argument("--include-training", action="store_true",
                        help="Also upload training artifacts")
    parser.add_argument("--tag", type=str, default=None,
                        help="Create a tag on HF repo (e.g. v2-models)")
    parser.add_argument("--v3", action="store_true",
                        help="Upload v3 candidate models from models/v3/")
    args = parser.parse_args()

    api = HfApi()
    user = api.whoami()
    print(f"Logged in as: {user['name']}")

    create_repo(REPO_ID, repo_type="model", exist_ok=True, private=False)
    print(f"Repo: https://huggingface.co/{REPO_ID}")

    # Stage files into a temp dir, then upload_folder in one commit
    with tempfile.TemporaryDirectory() as staging:
        staging = pathlib.Path(staging)

        files_to_upload = list(PRODUCTION_FILES)
        if args.include_training:
            files_to_upload += TRAINING_FILES

        copied = 0
        for fname in files_to_upload:
            src = MODELS / fname
            if not src.exists():
                print(f"  SKIP (not found): {fname}")
                continue
            size_mb = src.stat().st_size / (1024 * 1024)
            dst = staging / fname
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  Staged: {fname} ({size_mb:.1f} MB)")
            copied += 1

        if args.v3:
            v3_dir = MODELS / "v3"
            if v3_dir.exists():
                for f in sorted(v3_dir.iterdir()):
                    if f.is_file():
                        size_mb = f.stat().st_size / (1024 * 1024)
                        dst = staging / "v3" / f.name
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dst)
                        print(f"  Staged: v3/{f.name} ({size_mb:.1f} MB)")
                        copied += 1

        print(f"\nUploading {copied} files in one commit...")
        api.upload_folder(
            folder_path=str(staging),
            repo_id=REPO_ID,
            repo_type="model",
            commit_message=f"Upload {copied} model artifacts",
        )
        print("Upload complete!")

    if args.tag:
        api.create_tag(REPO_ID, tag=args.tag, repo_type="model")
        print(f"Tagged as: {args.tag}")

    print(f"\nAll {copied} files uploaded to https://huggingface.co/{REPO_ID}")
    print("\nTo download in production:")
    print("  from huggingface_hub import snapshot_download")
    print(f'  snapshot_download("{REPO_ID}", local_dir="models/")')


if __name__ == "__main__":
    main()
