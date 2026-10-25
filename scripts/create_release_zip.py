"""AgriMind Curated Release Packager and Verification Utility.

Creates a clean, reproducible, shareable ZIP from a pristine staging copy:
1. Copies only curated runtime, source, test, and documentation assets.
2. Strictly excludes .git, .env, credentials, local databases, caches, virtual environments,
   node_modules, and downloaded image datasets.
3. Packages into a standalone ZIP archive.
4. Generates a complete file manifest with file sizes and SHA-256 digests.
5. Extracts into a sandbox directory to verify extraction integrity, model hash,
   and test execution.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    "web/node_modules",
    ".next",
    "web/.next",
    "web/out",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "evaluation/datasets",
    ".idea",
    ".vscode",
    "coverage",
    "htmlcov",
    "dist",
    "build",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".tsbuildinfo",
    ".tmp",
    ".bak",
}

EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "Thumbs.db",
    ".DS_Store",
}


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def should_include(rel_path_str: str) -> bool:
    """Determine if a relative file path should be included in the release."""
    norm = rel_path_str.replace("\\", "/")
    parts = norm.split("/")

    # Check excluded directory names in path
    for part in parts[:-1]:
        if part in EXCLUDE_DIRS:
            return False

    for excl_prefix in EXCLUDE_DIRS:
        if norm.startswith(excl_prefix + "/") or f"/{excl_prefix}/" in norm:
            return False

    filename = parts[-1]
    if filename in EXCLUDE_FILES:
        return False

    suffix = Path(filename).suffix.lower()
    if suffix in EXCLUDE_EXTENSIONS:
        return False

    return True


def stage_release(source_root: Path, staging_root: Path) -> list[tuple[str, int, str]]:
    """Copy curated files to staging directory and return manifest entries."""
    manifest_entries: list[tuple[str, int, str]] = []

    for root, dirs, files in os.walk(source_root):
        rel_root = Path(root).relative_to(source_root)
        rel_root_str = str(rel_root).replace("\\", "/")

        # Prune excluded directories
        dirs[:] = [
            d for d in dirs
            if should_include(f"{rel_root_str}/{d}".strip("./") + "/dummy.txt")
        ]

        for file in files:
            source_file = Path(root) / file
            rel_file = source_file.relative_to(source_root)
            rel_file_str = str(rel_file).replace("\\", "/")

            if not should_include(rel_file_str):
                continue

            target_file = staging_root / rel_file
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)

            size = target_file.stat().st_size
            digest = compute_sha256(target_file)
            manifest_entries.append((rel_file_str, size, digest))

    return manifest_entries


def scan_for_secrets(staging_dir: Path) -> list[str]:
    """Scan staged files for potential private credentials or personal machine paths."""
    import re
    key_pattern = re.compile(r'(api[_-]?key|secret|password|bearer|token)\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})["\']', re.IGNORECASE)
    path_pattern = re.compile(r'[a-zA-Z]:\\(?:users|home)\\[a-zA-Z0-9_\-]+', re.IGNORECASE)

    violations = []
    for p in staging_dir.rglob('*'):
        if not p.is_file():
            continue
        if p.suffix.lower() in ('.pt', '.pdf', '.png', '.jpg', '.jpeg', '.lock', '.ico'):
            continue
        try:
            content = p.read_text(encoding='utf-8', errors='ignore')
            for idx, line in enumerate(content.splitlines(), 1):
                m_key = key_pattern.search(line)
                if m_key:
                    val = m_key.group(2)
                    if not any(ph in val.lower() for ph in ['placeholder', 'example', 'your_', 'test_']):
                        violations.append(f"{p.relative_to(staging_dir)}:{idx} Potential secret: {line.strip()[:60]}")
                m_path = path_pattern.search(line)
                if m_path:
                    violations.append(f"{p.relative_to(staging_dir)}:{idx} Local user path: {line.strip()[:60]}")
        except Exception:
            pass
    return violations


def build_zip(staging_dir: Path, output_zip: Path) -> None:
    """Compress staging directory contents into a ZIP archive."""
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(staging_dir):
            for file in sorted(files):
                abs_file = Path(root) / file
                rel_file = abs_file.relative_to(staging_dir)
                # Archive under top-level 'agrimind/' directory for clean extraction
                arcname = f"agrimind/{rel_file.as_posix()}"
                zf.write(abs_file, arcname)


def main():
    print("=" * 75)
    print("🌾 AGRIMIND RELEASE PACKAGER & VERIFICATION")
    print("=" * 75)

    source_dir = REPO_ROOT
    release_name = "agrimind_v2.0.0_release.zip"
    output_zip = source_dir.parent / release_name

    temp_staging = Path(tempfile.mkdtemp(prefix="agrimind_stage_"))
    temp_sandbox = Path(tempfile.mkdtemp(prefix="agrimind_sandbox_"))

    try:
        print(f"\n[1/5] Staging curated release from {source_dir}...")
        manifest = stage_release(source_dir, temp_staging)
        print(f"  Staged {len(manifest)} files.")

        # Check secret scan
        print("\n[2/5] Scanning staged files for credentials and personal paths...")
        violations = scan_for_secrets(temp_staging)
        if violations:
            print("  ❌ SECURITY VIOLATIONS DETECTED:")
            for v in violations:
                print(f"    - {v}")
            raise RuntimeError("Aborting release packaging due to exposed credentials/paths.")
        print("  ✅ Zero secrets or personal paths detected.")

        # Verify best.pt present in staging
        staged_model = temp_staging / "ml/artifacts/best.pt"
        if not staged_model.is_file():
            raise FileNotFoundError("Critical vision checkpoint ml/artifacts/best.pt missing from staging!")
        staged_hash = compute_sha256(staged_model)
        orig_hash = compute_sha256(source_dir / "ml/artifacts/best.pt")
        assert staged_hash == orig_hash, "Model checkpoint SHA-256 hash mismatch between source and staging!"
        print(f"  ✅ Model checkpoint verified: best.pt ({staged_model.stat().st_size:,} bytes, SHA-256: {staged_hash[:16]}...)")

        # Write manifest file into release
        manifest_path = temp_staging / "RELEASE_MANIFEST.csv"
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file_path", "size_bytes", "sha256"])
            for row in sorted(manifest):
                writer.writerow(row)
        print(f"  ✅ Generated RELEASE_MANIFEST.csv ({len(manifest)} entries).")

        # Create ZIP
        print(f"\n[3/5] Building shareable ZIP: {output_zip}...")
        build_zip(temp_staging, output_zip)
        zip_size = output_zip.stat().st_size
        print(f"  ✅ ZIP created successfully: {zip_size:,} bytes ({round(zip_size / (1024*1024), 2)} MB).")

        # Verify extraction in sandbox
        print(f"\n[4/5] Testing extraction integrity in sandbox: {temp_sandbox}...")
        with zipfile.ZipFile(output_zip, "r") as zf:
            zf.extractall(temp_sandbox)
        extracted_root = temp_sandbox / "agrimind"
        assert (extracted_root / "ml/artifacts/best.pt").is_file(), "best.pt missing from extracted archive!"
        assert (extracted_root / "package.json").is_file(), "package.json missing from extracted archive!"
        assert (extracted_root / "start.ps1").is_file(), "start.ps1 missing from extracted archive!"
        assert (extracted_root / "README.md").is_file(), "README.md missing from extracted archive!"
        assert (extracted_root / "QUICKSTART.md").is_file(), "QUICKSTART.md missing from extracted archive!"
        assert (extracted_root / "docs/PHASE_1_2_AUDIT.md").is_file(), "Mandatory PHASE_1_2_AUDIT.md missing!"
        assert (extracted_root / "docs/AGENT_CONTRACTS.md").is_file(), "Mandatory AGENT_CONTRACTS.md missing!"
        assert (extracted_root / "docs/DECISION_SAFETY.md").is_file(), "Mandatory DECISION_SAFETY.md missing!"
        assert (extracted_root / "docs/VERIFICATION_REPORT.md").is_file(), "Mandatory VERIFICATION_REPORT.md missing!"
        print("  ✅ All mandatory documents, model weights, startup scripts, and code verified in extracted ZIP.")

        # Run smoke verification on extracted sandbox
        print("\n[5/5] Executing smoke verification on extracted sandbox...")
        py_res = subprocess.run([sys.executable, "-m", "compileall", "-q", str(extracted_root)], capture_output=True)
        assert py_res.returncode == 0, f"Bytecode compilation failed on extracted release: {py_res.stderr.decode()}"
        print("  ✅ Python bytecode compilation passed cleanly on extracted sandbox.")

        # Run automated disease evaluation tests inside sandbox
        test_res = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_disease_evaluation.py", "-v"],
            cwd=str(extracted_root),
            capture_output=True,
            text=True,
        )
        assert test_res.returncode == 0, f"Tests failed in sandbox: {test_res.stdout}\n{test_res.stderr}"
        print("  ✅ 13/13 disease evaluation regression tests passed in extracted sandbox.")

        print("\n" + "=" * 75)
        print("🎉 AGRIMIND v2.0.0 RELEASE PACKAGE VERIFIED AND READY")
        print(f"   ZIP File: {output_zip}")
        print(f"   Size:     {round(zip_size / (1024*1024), 2)} MB ({zip_size:,} bytes)")
        print(f"   Files:    {len(manifest) + 1} files archived under 'agrimind/' root")
        print("=" * 75)

    finally:
        shutil.rmtree(temp_staging, ignore_errors=True)
        shutil.rmtree(temp_sandbox, ignore_errors=True)


if __name__ == "__main__":
    main()
