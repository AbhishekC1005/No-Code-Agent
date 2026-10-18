#!/usr/bin/env python3
"""
Cross-platform build script for No-Code Agent.
Builds the React frontend and copies the compiled dist files
into the backend's static directory for packaging and single-command serving.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
STATIC_DIR = ROOT_DIR / "backend" / "nocode_agent" / "static"


def run_command(cmd: list[str], cwd: Path):
    cmd_str = " ".join(cmd)
    print(f"==> Running: {cmd_str} in {cwd}")
    shell = sys.platform == "win32"
    result = subprocess.run(cmd, cwd=cwd, shell=shell)
    if result.returncode != 0:
        print(f"Error: Command failed with code {result.returncode}: {cmd_str}")
        sys.exit(result.returncode)


def main():
    print("========================================")
    print("Building No-Code Agent (Frontend -> Dist)")
    print("========================================")

    # 1. Check node_modules
    if not (FRONTEND_DIR / "node_modules").is_dir():
        print("node_modules not found. Running npm install...")
        run_command(["npm", "install"], cwd=FRONTEND_DIR)

    # 2. Build frontend
    print("Building frontend with Vite...")
    run_command(["npm", "run", "build"], cwd=FRONTEND_DIR)

    if not DIST_DIR.is_dir():
        print(f"Error: Expected build output at {DIST_DIR} not found.")
        sys.exit(1)

    # 3. Copy to backend/nocode_agent/static
    print(f"Copying {DIST_DIR} -> {STATIC_DIR}...")
    if STATIC_DIR.exists():
        shutil.rmtree(STATIC_DIR)
    shutil.copytree(DIST_DIR, STATIC_DIR)

    print("========================================")
    print("Build complete! Frontend bundled successfully.")
    print("You can now run: nocode-agent start")
    print("========================================")


if __name__ == "__main__":
    main()
