"""
Overnight training runner — launches all retraining scripts in sequence.

Run before bed:
  python scripts/run_overnight.py

Timeline:
  1. Hybrid weight optimization  (~30-60 min, CPU)
  2. NeuMF v3                    (~4-5 hours, GPU)
  3. FunkSVD v3                  (~6-8 hours, CPU)

Total: ~12-14 hours. Results saved to models/v3/

After waking up, check results:
  python scripts/compare_all_versions.py
"""
import os
import subprocess
import sys
import time
from datetime import datetime

os.environ["PYTHONIOENCODING"] = "utf-8"

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPTS_DIR, "..", ".venv", "Scripts", "python.exe")

# Use venv python if available, otherwise system python
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable
    print(f"WARNING: venv not found, using {VENV_PYTHON}")


def run_script(name, script_path):
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting: {name}")
    print(f"{'='*70}\n")

    t0 = time.time()
    result = subprocess.run(
        [VENV_PYTHON, script_path],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    elapsed = (time.time() - t0) / 60

    status = "OK" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {name}: {status} ({elapsed:.1f} min)")
    return result.returncode == 0


def main():
    print(f"Overnight Training Runner")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {VENV_PYTHON}")

    results = {}
    t_start = time.time()

    # 1. Hybrid weight optimization (fast, run first)
    results["hybrid"] = run_script(
        "Hybrid Weight Optimization",
        os.path.join(SCRIPTS_DIR, "optimize_hybrid_weights.py")
    )

    # 2. NeuMF v3 (GPU)
    results["neumf"] = run_script(
        "NeuMF v3 Retraining",
        os.path.join(SCRIPTS_DIR, "retrain_neumf_v3.py")
    )

    # 3. FunkSVD v3 (CPU, longest)
    results["funksvd"] = run_script(
        "FunkSVD v3 Retraining",
        os.path.join(SCRIPTS_DIR, "retrain_funksvd_v3.py")
    )

    # Summary
    total = (time.time() - t_start) / 3600
    print(f"\n{'='*70}")
    print(f"OVERNIGHT TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"Total time: {total:.1f} hours")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    for name, ok in results.items():
        print(f"  {name:<20} {'PASSED' if ok else 'FAILED'}")

    print(f"\nNext steps:")
    print(f"  1. Review results in models/v3/")
    print(f"  2. Compare: python scripts/compare_all_versions.py")
    print(f"  3. If improved, promote and deploy")


if __name__ == "__main__":
    main()
