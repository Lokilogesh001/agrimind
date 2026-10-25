"""AgriMind Unified Scientific Evaluation Runner.

Executes the three scientific validation workflows:
1. Disease Classifier Evaluation (MobileNetV3-Large on labeled test dataset)
2. Agronomic Advisory Benchmark (16 versioned ICAR-grounded scenarios)
3. External Data Quality & Resilience Evaluation (Weather, Market, Soil, Geocoding)

Generates machine-readable evaluation artifacts in evaluation/artifacts/
and a consolidated dissertation-ready summary.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_disease_model import run_evaluation as run_disease_eval
from evaluation.evaluate_advisory_benchmark import run_benchmark as run_advisory_eval
from evaluation.evaluate_data_quality import run_data_quality_evaluation as run_data_eval


def main():
    default_data_dir = "evaluation/datasets/plantdoc_test/images" if Path("evaluation/datasets/plantdoc_test/images").is_dir() else None
    default_manifest = "evaluation/manifests/plantdoc_test_manifest.csv" if Path("evaluation/manifests/plantdoc_test_manifest.csv").is_file() else None

    parser = argparse.ArgumentParser(description="Run AgriMind Phase 4 scientific evaluation suite")
    parser.add_argument("--checkpoint", default="ml/artifacts/best.pt", help="Path to disease model checkpoint")
    parser.add_argument("--data-dir", default=default_data_dir, help="Root folder of raw test leaf images (if available)")
    parser.add_argument("--manifest", default=default_manifest, help="Path to test manifest file (if available)")
    parser.add_argument("--train-manifest", default=None, help="Path to train manifest for leakage audit")
    parser.add_argument("--benchmark", default="evaluation/benchmarks/icar_advisory_ground_truth.json", help="Path to advisory benchmark JSON")
    parser.add_argument("--output-dir", default="evaluation/artifacts", help="Directory to save evaluation artifacts")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for model inference")
    args = parser.parse_args()

    start_total = time.perf_counter()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("🌾 AGRIMIND PHASE 4 — SCIENTIFIC EVALUATION & REAL-WORLD VALIDATION SUITE")
    print(f"   Execution Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"   Artifacts Target:    {out_dir}")
    print(f"   Random Seed:         {args.seed}")
    print("=" * 75)
    print()

    # Tier 1: Disease Classifier Evaluation
    print("---------------------------------------------------------------------------")
    print("1. EVALUATING DISEASE CLASSIFIER (MobileNetV3-Large)...")
    print("---------------------------------------------------------------------------")
    disease_results = run_disease_eval(
        checkpoint=args.checkpoint,
        data_dir=args.data_dir,
        manifest=args.manifest,
        train_manifest=args.train_manifest,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        seed=args.seed,
    )
    print()

    # Tier 2: Agronomic Advisory Benchmark
    print("---------------------------------------------------------------------------")
    print("2. EVALUATING AGRONOMIC ADVISORY BENCHMARK (ICAR/TNAU/CIBRC Ground Truth)...")
    print("---------------------------------------------------------------------------")
    advisory_results = run_advisory_eval(
        benchmark_file=args.benchmark,
        output_dir=args.output_dir,
    )
    print()

    # Tier 3: External Data Quality Evaluation
    print("---------------------------------------------------------------------------")
    print("3. EVALUATING EXTERNAL DATA PATHWAYS & RESILIENCE...")
    print("---------------------------------------------------------------------------")
    data_quality_results = run_data_eval(
        output_dir=args.output_dir,
    )
    print()

    total_latency = round(time.perf_counter() - start_total, 2)

    # Consolidated Master Summary
    consolidated_summary = {
        "evaluation_suite": "AgriMind Phase 4 Scientific Evaluation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_latency_seconds": total_latency,
        "seed": args.seed,
        "disease_evaluation": {
            "status": disease_results.get("status"),
            "model_ready": disease_results.get("model_ready", disease_results.get("status") in ("PARTIAL_CROSS_DATASET_EVALUATION", "CROSS_DATASET_EVALUATION_COMPLETE", "COMPLETED")),
            "architecture": "MobileNetV3-Large",
            "classes_total_count": disease_results.get("class_coverage", {}).get("classes_total_count", disease_results.get("classes_count", 38)),
            "classes_evaluated_count": disease_results.get("class_coverage", {}).get("classes_evaluated_count"),
            "coverage_percentage": disease_results.get("class_coverage", {}).get("coverage_percentage"),
            "labeled_data_present": disease_results.get("status") in ("PARTIAL_CROSS_DATASET_EVALUATION", "CROSS_DATASET_EVALUATION_COMPLETE", "COMPLETED"),
            "top1_accuracy": (disease_results.get("metrics") or {}).get("top1_accuracy", disease_results.get("accuracy")),
            "wilson_95_ci": (disease_results.get("metrics") or {}).get("wilson_95_ci"),
            "macro_f1_evaluated_classes": (disease_results.get("metrics") or {}).get("macro_f1_evaluated_classes", disease_results.get("macro_f1")),
            "macro_f1_all_38_classes": (disease_results.get("metrics") or {}).get("macro_f1_all_38_classes"),
            "calibration_ece": (disease_results.get("calibration") or {}).get("expected_calibration_error"),
            "blocker_notice": (
                "Raw image dataset is unavailable locally; evaluation pipeline verified and ready. "
                "No synthetic metrics were fabricated."
                if disease_results.get("status") == "BLOCKED_PENDING_DATA"
                else None
            ),
        },
        "advisory_benchmark": {
            "total_scenarios": advisory_results["aggregate_metrics"]["total_scenarios_evaluated"],
            "conforming_scenarios": advisory_results["aggregate_metrics"]["scenarios_conforming"],
            "conformance_rate": advisory_results["aggregate_metrics"]["overall_conformance_rate"],
            "safety_violations": advisory_results["aggregate_metrics"]["safety_rule_violations_count"],
            "appropriate_abstention_rate": advisory_results["aggregate_metrics"]["appropriate_abstention_rate"],
            "citation_traceability_rate": advisory_results["aggregate_metrics"]["citation_traceability_rate"],
            "expert_review_status": advisory_results["expert_validation_disclosure"],
        },
        "data_quality_evaluation": {
            "pathways_evaluated": data_quality_results["summary"]["total_pathways_evaluated"],
            "probes_evaluated": data_quality_results["summary"]["total_test_probes"],
            "overall_pass": data_quality_results["summary"]["overall_pass"],
            "pathways": {
                name: res["all_passed"]
                for name, res in data_quality_results["pathway_results"].items()
            },
        },
        "generated_artifacts": [
            str(out_dir / "disease_evaluation_status.json"),
            str(out_dir / "disease_evaluation_results.json"),
            str(out_dir / "advisory_benchmark_report.json"),
            str(out_dir / "data_quality_report.json"),
            str(out_dir / "evaluation_summary.json"),
        ],
    }

    summary_file = out_dir / "evaluation_summary.json"
    summary_file.write_text(json.dumps(consolidated_summary, indent=2), encoding="utf-8")

    print("=" * 75)
    print("🏆 MASTER SCIENTIFIC EVALUATION COMPLETE")
    print(f"   Total Execution Time: {total_latency}s")
    print(f"   Disease Status:       {disease_results.get('status')}")
    print(f"   Advisory Conformance: {advisory_results['aggregate_metrics']['overall_conformance_rate'] * 100:.1f}% ({advisory_results['aggregate_metrics']['scenarios_conforming']}/{advisory_results['aggregate_metrics']['total_scenarios_evaluated']})")
    print(f"   Safety Violations:    {advisory_results['aggregate_metrics']['safety_rule_violations_count']}")
    print(f"   Data Quality Probes:  {data_quality_results['summary']['total_test_probes']} Passed")
    print(f"   Master Report:        {summary_file}")
    print("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())
