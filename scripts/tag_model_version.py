"""
Tag the current model artifacts as a DVC version.

After retraining and promoting models, run this to:
1. Update DVC tracking (models.dvc hash)
2. Create a git tag with the model version

Usage:
  python scripts/tag_model_version.py v1    # tag current models as v1
  python scripts/tag_model_version.py v2    # tag after retraining as v2

To restore a previous version:
  git checkout v1-models -- models.dvc
  dvc checkout models.dvc
"""
import subprocess
import sys

if len(sys.argv) < 2:
    print("Usage: python scripts/tag_model_version.py <version>")
    print("Example: python scripts/tag_model_version.py v1")
    sys.exit(1)

version = sys.argv[1]
tag_name = f"{version}-models"

print(f"Tagging current models as '{tag_name}'...")

# Update DVC tracking
print("\n1. Updating DVC tracking...")
subprocess.run([sys.executable, "-m", "dvc", "add", "models/"], check=True)
subprocess.run([sys.executable, "-m", "dvc", "add", "data_science/processed/"], check=True)

# Stage and commit
print("\n2. Committing DVC files...")
subprocess.run(["git", "add", "models.dvc", "data_science/processed.dvc"], check=True)
subprocess.run([
    "git", "commit", "-m",
    f"Track model artifacts {version}\n\nDVC-tracked model version: {version}"
], check=True)

# Create git tag
print(f"\n3. Creating tag '{tag_name}'...")
subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Model artifacts {version}"], check=True)

print(f"\n{'='*50}")
print(f"Tagged as '{tag_name}'")
print(f"{'='*50}")
print(f"\nTo restore this version later:")
print(f"  git checkout {tag_name} -- models.dvc")
print(f"  python -m dvc checkout models.dvc")
print(f"\nTo push tag to remote:")
print(f"  git push origin {tag_name}")
