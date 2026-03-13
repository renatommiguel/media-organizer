"""Build a portable single-file executable using PyInstaller."""

import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent

def main():
    with tempfile.TemporaryDirectory() as tmp:
        venv_dir = Path(tmp) / ".venv"

        print("Creating clean build environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        pip = str(venv_dir / "Scripts" / "pip.exe")
        python = str(venv_dir / "Scripts" / "python.exe")

        print("Installing only required dependencies...")
        subprocess.run([pip, "install", "-q",
            "blake3", "Pillow", "tqdm", "imagehash",
            "reverse_geocoder", "pyinstaller",
        ], check=True)

        print("Installing media-organizer package...")
        subprocess.run([pip, "install", "-q", "-e", str(ROOT)], check=True)

        print("Building executable...")
        dist = ROOT / "dist"
        vendor_src = ROOT / "vendor"
        subprocess.run([
            python, "-m", "PyInstaller",
            "--onefile",
            "--name", "media-organizer",
            "--clean",
            "--add-data", f"{vendor_src};vendor",
            "--distpath", str(dist),
            "--workpath", str(Path(tmp) / "build"),
            "--specpath", str(tmp),
            str(ROOT / "entry.py"),
        ], check=True)

        exe = dist / "media-organizer.exe"
        print(f"\nDone! Executable: {exe}")
        print(f"Size: {exe.stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    main()
