r"""
AgriMind Core Deliverable Verification Script.
Verifies the clean, lightweight archive at D:/project/AGRIMIND/demo/dist/AgriMind_Core.zip.
Tests unzipping, checksums, import integrity, execution, and zero leaks.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_ZIP = Path("D:/project/AGRIMIND/demo/dist/AgriMind_Core.zip")
SUMMARY_TXT = Path("D:/project/AGRIMIND/demo/dist/CLEANUP_SUMMARY.txt")
DOC_PATH = ROOT / "AgriMind_Complete_Documentation.md"

FORBIDDEN_KEYWORDS = [
    "tests/",
    "evaluation/",
    ".venv/",
    "node_modules/",
    ".next/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    ".db",
    ".sqlite",
    ".git/",
    "research/",
    "train_disease.py",
    "train_field_finetune.py",
    "ICAR-En-Kharif-Agro-Advisories-for-Farmers-2025.pdf",
]


def get_python_exe() -> str:
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def compute_sha256(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def test_archive_exists():
    print("=" * 70)
    print("CHECK 1: ARCHIVE EXISTENCE & SIZE VERIFICATION")
    print("=" * 70)

    assert TARGET_ZIP.exists(), f"Target ZIP not found at {TARGET_ZIP}"
    sz = TARGET_ZIP.stat().st_size
    print(f"Archive path: {TARGET_ZIP.resolve()}")
    print(f"Archive size: {sz / (1024*1024):.2f} MB ({sz:,} bytes)")
    assert sz > 1000, f"Archive too small: {sz} bytes"
    assert sz < 150 * 1024 * 1024, f"Archive unexpectedly large: {sz} bytes"
    print("PASS: Archive exists and size is within expected lightweight range (<150 MB).")

    assert SUMMARY_TXT.exists(), f"Cleanup summary missing at {SUMMARY_TXT}"
    print(f"PASS: Cleanup summary exists at {SUMMARY_TXT.resolve()}")


def test_archive_manifest_and_zero_leaks():
    print("\n" + "=" * 70)
    print("CHECK 2: ARCHIVE FILE LISTING & ZERO LEAKS")
    print("=" * 70)

    with zipfile.ZipFile(TARGET_ZIP, "r") as zf:
        infolist = zf.infolist()
        files = [info.filename for info in infolist]
        print(f"Total files in archive: {len(files)}")

        leaks = []
        for fn in files:
            fn_lower = fn.lower()
            if fn_lower.endswith("/.env") or fn_lower == "agrimind_core/.env":
                leaks.append((fn, "exact .env file"))
            for kw in FORBIDDEN_KEYWORDS:
                if kw in fn_lower:
                    leaks.append((fn, kw))

        assert not leaks, f"LEAKS DETECTED IN ARCHIVE: {leaks}"
        print(f"PASS: Zero forbidden patterns detected among all {len(files)} archived files.")

        # Verify critical signatures
        must_have = [
            "AgriMind_Core/main.py",
            "AgriMind_Core/start.ps1",
            "AgriMind_Core/start.sh",
            "AgriMind_Core/requirements.txt",
            "AgriMind_Core/package.json",
            "AgriMind_Core/.env.example",
            "AgriMind_Core/PACKAGE_CONTENTS.md",
            "AgriMind_Core/AgriMind_Complete_Documentation.md",
            "AgriMind_Core/CLEANUP_SUMMARY.txt",
            "AgriMind_Core/api/main.py",
            "AgriMind_Core/agents/disease_agent.py",
            "AgriMind_Core/agents/weather_agent.py",
            "AgriMind_Core/agents/soil_agent.py",
            "AgriMind_Core/decision/safety_guard.py",
            "AgriMind_Core/decision/evidence_engine.py",
            "AgriMind_Core/ml/dinov2_adapter.py",
            "AgriMind_Core/ml/disease_model.py",
            "AgriMind_Core/ml/model_registry.py",
            "AgriMind_Core/ml/artifacts/dinov2_lora_r4_b4_best.pt",
            "AgriMind_Core/ml/artifacts/best.pt",
            "AgriMind_Core/ml/artifacts/MODEL_MANIFEST.json",
            "AgriMind_Core/ml/artifacts/MODELS_README.md",
            "AgriMind_Core/knowledge/icar_chunks.json",
            "AgriMind_Core/scripts/clean.js",
            "AgriMind_Core/scripts/dev.js",
            "AgriMind_Core/scripts/start.js",
            "AgriMind_Core/web/package.json",
            "AgriMind_Core/web/app/components/FarmInputForm.tsx",
            "AgriMind_Core/web/app/components/AdvisoryHero.tsx",
        ]
        missing = [req for req in must_have if req not in files]
        assert not missing, f"Missing critical files: {missing}"
        print(f"PASS: All {len(must_have)} critical files verified inside archive.")


def test_checkpoint_hashes():
    print("\n" + "=" * 70)
    print("CHECK 3: CHECKPOINT INTEGRITY & SHA-256 VERIFICATION")
    print("=" * 70)

    with zipfile.ZipFile(TARGET_ZIP, "r") as zf:
        manifest_raw = zf.read("AgriMind_Core/ml/artifacts/MODEL_MANIFEST.json")
        manifest = json.loads(manifest_raw.decode("utf-8"))

        dinov2_entry = manifest["models"]["dinov2_lora"]
        expected_dinov2_sha256 = dinov2_entry["expected_sha256"]

        mobilenet_entry = manifest["models"]["production"]
        expected_mobilenet_sha256 = mobilenet_entry["expected_sha256"]

        print(f"Verifying DINOv2 LoRA checkpoint in archive...")
        dinov2_bytes = zf.read("AgriMind_Core/ml/artifacts/dinov2_lora_r4_b4_best.pt")
        actual_dinov2_sha256 = compute_sha256(dinov2_bytes)
        print(f"  Expected: {expected_dinov2_sha256}")
        print(f"  Actual:   {actual_dinov2_sha256}")
        assert actual_dinov2_sha256 == expected_dinov2_sha256, "DINOv2 LoRA SHA-256 mismatch!"
        print("PASS: DINOv2 LoRA checkpoint hash matches manifest exactly.")

        print(f"Verifying MobileNetV3 rollback checkpoint in archive...")
        mobilenet_bytes = zf.read("AgriMind_Core/ml/artifacts/best.pt")
        actual_mobilenet_sha256 = compute_sha256(mobilenet_bytes)
        print(f"  Expected: {expected_mobilenet_sha256}")
        print(f"  Actual:   {actual_mobilenet_sha256}")
        assert actual_mobilenet_sha256 == expected_mobilenet_sha256, "MobileNetV3 SHA-256 mismatch!"
        print("PASS: MobileNetV3 checkpoint hash matches manifest exactly.")


def test_extracted_execution():
    print("\n" + "=" * 70)
    print("CHECK 4: EXTRACTION, MODULE IMPORTS & END-TO-END VERIFICATION")
    print("=" * 70)

    py_exe = get_python_exe()
    print(f"Using Python runtime: {py_exe}")

    temp_dir = Path(tempfile.mkdtemp(prefix="agrimind_core_test_"))
    try:
        with zipfile.ZipFile(TARGET_ZIP, "r") as zf:
            zf.extractall(temp_dir)

        core_dir = temp_dir / "AgriMind_Core"
        assert core_dir.exists(), "Extracted folder AgriMind_Core not found!"

        test_code = """
import sys
from pathlib import Path
root = Path(".").resolve()
sys.path.insert(0, str(root))

# Import all core modules
import agents.weather_agent
import agents.soil_agent
import agents.disease_agent
import agents.market_agent
import agents.advisory_agent
import api.main
import data_sources.crops
import data_sources.weather
import data_sources.soil
import data_sources.market
import data_sources.geocoding
import data_sources.stores
import data_sources.treatments
import decision.evidence_engine
import decision.safety_guard
import decision.scoring
import decision.rules
import llm.explainer
import ml.dinov2_adapter
import ml.disease_model
import ml.model_registry
import observability.database
import orchestrator.graph
import orchestrator.state
import rag.retriever

print("All core modules imported successfully from extracted archive!")

# Test model health
from ml.dinov2_adapter import get_dinov2_health
from ml.disease_model import get_model_health
d_health = get_dinov2_health()
m_health = get_model_health()
print("DINOv2 health:", d_health["status"], "ready:", d_health["ready"])
print("MobileNet health:", m_health["status"], "ready:", m_health["ready"])
assert d_health["ready"] == True, f"DINOv2 not ready: {d_health}"
assert m_health["ready"] == True, f"MobileNet not ready: {m_health}"

# Test orchestrator
from orchestrator.graph import run_advisory
state = run_advisory({
    "weather_override": {"precip_prob": 0.90, "intensity": 0.8, "duration": 0.75},
    "n": 20, "p": 45, "k": 70,
    "current_price": 2200, "price_history": [1900, 2000, 2200]
})
assert state.final_recommendation == "DELAY", f"Unexpected rec: {state.final_recommendation}"
print(f"End-to-end advisory execution passed! Final rec: {state.final_recommendation}")
"""
        res = subprocess.run(
            [py_exe, "-c", test_code],
            cwd=str(core_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        print("Extracted execution stdout:\n", res.stdout)
        if res.stderr:
            print("Extracted execution stderr:\n", res.stderr)
        assert res.returncode == 0, f"Extracted execution failed with code {res.returncode}"
        print("PASS: Extracted archive runs cleanly with zero missing files or broken imports!")

        # Verify startup scripts point to existing files
        print("\nVerifying startup script targets in extracted archive...")
        assert (core_dir / "start.ps1").exists(), "start.ps1 missing"
        assert (core_dir / "start.sh").exists(), "start.sh missing"
        assert (core_dir / "main.py").exists(), "main.py missing"
        assert (core_dir / "api" / "main.py").exists(), "api/main.py missing"
        assert (core_dir / "web" / "package.json").exists(), "web/package.json missing"
        assert (core_dir / "web" / "app" / "components" / "FarmInputForm.tsx").exists(), "FarmInputForm.tsx missing"
        print("PASS: All startup targets verified in extracted directory.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_frontend_build_artifacts():
    print("\n" + "=" * 70)
    print("CHECK 5: FRONTEND STATUS IN ARCHIVE")
    print("=" * 70)

    with zipfile.ZipFile(TARGET_ZIP, "r") as zf:
        web_files = [f for f in zf.namelist() if f.startswith("AgriMind_Core/web/")]
        print(f"Total web files in archive: {len(web_files)}")

        # Ensure no node_modules or .next
        for f in web_files:
            assert "node_modules" not in f, f"node_modules leaked into archive: {f}"
            assert ".next" not in f, f".next build leaked into archive: {f}"
            assert "tsbuildinfo" not in f, f"tsbuildinfo leaked into archive: {f}"

        # Ensure all 19 React components are present
        components = [f for f in web_files if "app/components/" in f]
        print(f"React UI components present: {len(components)}")
        assert len(components) == 19, f"Expected 19 components, found {len(components)}"
        print("PASS: Clean web application with all 19 approved UI components verified.")


def main():
    test_archive_exists()
    test_archive_manifest_and_zero_leaks()
    test_checkpoint_hashes()
    test_extracted_execution()
    test_frontend_build_artifacts()
    print("\n" + "=" * 70)
    print("ALL CORE VERIFICATION CHECKS PASSED (100% GREEN)")
    print("=" * 70)


if __name__ == "__main__":
    main()
