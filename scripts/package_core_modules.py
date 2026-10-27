r"""
AgriMind Clean Core Packaging Script.
Builds D:\project\AGRIMIND\demo\dist\AgriMind_Core.zip.
Contains ONLY genuine runtime core files, models, knowledge corpus, frontend, and runner scripts.
Zero tests, zero research datasets, zero caches.
"""
from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO_DIST = Path("D:/project/AGRIMIND/demo/dist")
LOCAL_DIST = ROOT / "dist"
OUTPUT_ZIP = DEMO_DIST / "AgriMind_Core.zip"
ZIP_PREFIX = "AgriMind_Core"

EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".db", ".sqlite", ".sqlite3", ".log", ".tmp"}
EXCLUDE_NAMES = {
    ".env",
    ".git",
    ".github",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    "node_modules",
    ".next",
    ".venv",
    "venv",
    "env",
    "tests",
    "evaluation",
    "research",
    "dist",
    "agrimind_local.db",
    "tsconfig.tsbuildinfo",
}

ALLOW_ROOT_FILES = [
    "main.py",
    "start.ps1",
    "start.sh",
    "requirements.txt",
    "package.json",
    ".env.example",
    ".gitignore",
    "README.md",
    "Dockerfile",
    "docker-compose.yml",
    "PACKAGE_CONTENTS.md",
    "AgriMind_Complete_Documentation.md",
    "CLEANUP_SUMMARY.txt",
]

CORE_DIRS = [
    "agents",
    "api",
    "data_sources",
    "decision",
    "llm",
    "observability",
    "orchestrator",
    "rag",
]

RUNNER_SCRIPTS = [
    "clean.js",
    "dev.js",
    "start.js",
]


def collect_files():
    files_to_pack = []

    # 1. Root files
    for fname in ALLOW_ROOT_FILES:
        p = ROOT / fname
        if p.exists() and p.is_file():
            files_to_pack.append((p, f"{ZIP_PREFIX}/{fname}"))
        else:
            print(f"WARNING: Root file {fname} not found!")

    # 2. Core Python modules
    for dname in CORE_DIRS:
        dp = ROOT / dname
        if not dp.exists():
            print(f"WARNING: Directory {dname} does not exist!")
            continue
        for p in dp.rglob("*"):
            if p.is_file():
                if any(part in EXCLUDE_NAMES for part in p.parts):
                    continue
                if p.suffix in EXCLUDE_EXTENSIONS:
                    continue
                rel_path = p.relative_to(ROOT).as_posix()
                files_to_pack.append((p, f"{ZIP_PREFIX}/{rel_path}"))

    # 3. Knowledge runtime asset (icar_chunks.json)
    knowledge_chunk = ROOT / "knowledge" / "icar_chunks.json"
    if knowledge_chunk.exists():
        files_to_pack.append((knowledge_chunk, f"{ZIP_PREFIX}/knowledge/icar_chunks.json"))
    else:
        print("ERROR: knowledge/icar_chunks.json missing!")

    # 4. ML core modules & artifacts (DINOv2 LoRA + MobileNet rollback + manifests)
    ml_dir = ROOT / "ml"
    for p in ml_dir.glob("*.py"):
        if p.is_file():
            rel_path = p.relative_to(ROOT).as_posix()
            files_to_pack.append((p, f"{ZIP_PREFIX}/{rel_path}"))
    ml_readme = ml_dir / "README.md"
    if ml_readme.exists():
        files_to_pack.append((ml_readme, f"{ZIP_PREFIX}/ml/README.md"))

    artifacts_dir = ml_dir / "artifacts"
    for artifact_name in [
        "dinov2_lora_r4_b4_best.pt",
        "best.pt",
        "MODEL_MANIFEST.json",
        "MODELS_README.md",
    ]:
        ap = artifacts_dir / artifact_name
        if ap.exists():
            files_to_pack.append((ap, f"{ZIP_PREFIX}/ml/artifacts/{artifact_name}"))
        else:
            print(f"WARNING: Artifact {artifact_name} missing from ml/artifacts!")

    # 5. Runtime scripts (clean.js, dev.js, start.js)
    scripts_dir = ROOT / "scripts"
    for sname in RUNNER_SCRIPTS:
        sp = scripts_dir / sname
        if sp.exists():
            files_to_pack.append((sp, f"{ZIP_PREFIX}/scripts/{sname}"))

    # 6. Frontend web application (excluding node_modules, .next, tsbuildinfo)
    web_dir = ROOT / "web"
    for p in web_dir.rglob("*"):
        if p.is_file():
            if any(part in EXCLUDE_NAMES for part in p.parts):
                continue
            if p.name in ("tsconfig.tsbuildinfo", ".DS_Store"):
                continue
            rel_path = p.relative_to(ROOT).as_posix()
            files_to_pack.append((p, f"{ZIP_PREFIX}/{rel_path}"))

    return files_to_pack


def verify_manifest(files_to_pack):
    print("=" * 70)
    print("CORE PACKAGE VERIFICATION CHECKS")
    print("=" * 70)

    forbidden_patterns = [
        "tests/",
        "evaluation/",
        ".venv/",
        "node_modules/",
        ".next/",
        "__pycache__/",
        ".pytest_cache/",
        ".db",
        ".sqlite",
        ".git/",
        "ml/research/",
        "ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf",
    ]

    leaks = []
    for abs_p, arc_p in files_to_pack:
        arc_p_lower = arc_p.lower()
        if arc_p_lower.endswith("/.env") or arc_p_lower == f"{ZIP_PREFIX.lower()}/.env":
            leaks.append((arc_p, "exact .env file"))
        for forbidden in forbidden_patterns:
            if forbidden in arc_p_lower:
                leaks.append((arc_p, forbidden))

    if leaks:
        print(f"FAILED: Found {len(leaks)} forbidden files in archive manifest!")
        for arc_p, reason in leaks[:10]:
            print(f"  - {arc_p} matches '{reason}'")
        sys.exit(1)
    else:
        print("PASS: Zero forbidden patterns detected in archive manifest.")


def build_core_zip():
    DEMO_DIST.mkdir(parents=True, exist_ok=True)
    LOCAL_DIST.mkdir(parents=True, exist_ok=True)

    files = collect_files()
    verify_manifest(files)

    print(f"\nCompressing {len(files)} files into {OUTPUT_ZIP}...")
    total_uncompressed = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for abs_p, arc_p in sorted(files, key=lambda x: x[1]):
            zf.write(abs_p, arcname=arc_p)
            total_uncompressed += abs_p.stat().st_size

    # Also copy to local dist for redundancy
    local_copy = LOCAL_DIST / "AgriMind_Core.zip"
    shutil.copy2(OUTPUT_ZIP, local_copy)

    # Also create copy of CLEANUP_SUMMARY.txt in demo/dist
    shutil.copy2(ROOT / "CLEANUP_SUMMARY.txt", DEMO_DIST / "CLEANUP_SUMMARY.txt")

    zip_size = OUTPUT_ZIP.stat().st_size
    print("=" * 70)
    print("AGRIMIND CORE ARCHIVE GENERATED")
    print("=" * 70)
    print(f"Primary Output:     {OUTPUT_ZIP.resolve()}")
    print(f"Local Mirror:       {local_copy.resolve()}")
    print(f"Total Files:        {len(files)}")
    print(f"Uncompressed Size:  {total_uncompressed / (1024 * 1024):.2f} MB ({total_uncompressed:,} bytes)")
    print(f"Compressed Size:    {zip_size / (1024 * 1024):.2f} MB ({zip_size:,} bytes)")
    print(f"Compression Ratio:  {zip_size / total_uncompressed * 100:.1f}%")
    print("=" * 70)


if __name__ == "__main__":
    build_core_zip()
