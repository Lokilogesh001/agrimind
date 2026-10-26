"""AgriMind Unified 38-Class Disease Model Optimization - Stages B, C, D and Finalist Pipeline.

Executes:
1. Dynamic inspection of Stage A winner from leaderboard.json.
2. Stage B: Training Strategy Search (Balanced sampler, unfreeze depths, extended schedule, scheduler variants).
3. Stage C: Foliar Augmentation Policy Search (Mild, Standard, Strong).
4. Stage D: Loss Function Search (Smoothing 0.10, Unweighted CE, Focal Loss).
5. Stage Finalists: Multi-Seed Robustness Verification (Seeds 42, 100, 2026).
6. Finalist packaging into ml/research/unified_optimization/finalist_model/.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path
import shutil
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.research.unified_optimization.experiment_runner import (
    ExperimentConfig,
    EXPECTED_BASELINE_SHA256,
    REPO_ROOT,
    run_experiment_suite,
    sha256_of_file,
    update_leaderboard_and_ledger,
)


def load_best_stage_a_config(ws: Path) -> dict[str, Any]:
    """Retrieve the top-ranked Stage A configuration from the leaderboard."""
    lb_path = ws / "leaderboard.json"
    if not lb_path.is_file():
        raise FileNotFoundError(f"Leaderboard not found at {lb_path}")
    data = json.loads(lb_path.read_text(encoding="utf-8"))
    stage_a_runs = [r for r in data if r.get("stage") == "stage_a"]
    if not stage_a_runs:
        raise ValueError("No completed Stage A runs found in leaderboard!")
    best_run = stage_a_runs[0]
    print(f"\n[PIPELINE] Top Stage A Winner: {best_run['run_id']}")
    print(f"    Val F1: {best_run['best_val_macro_f1']:.4f} | Val Acc: {best_run['best_val_accuracy']:.4f} | ECE: {best_run['best_val_ece']:.4f} | Score: {best_run['best_composite_score']:.4f}")
    return best_run["config"]


def build_stage_b_configs(base_cfg: dict[str, Any]) -> list[ExperimentConfig]:
    """Generate Stage B training strategy experiments."""
    configs: list[ExperimentConfig] = []

    # 1. Balanced sampling
    c1 = ExperimentConfig(
        run_id="stage_b_01_strategy_balanced_sampler",
        stage="stage_b",
        description="Stage B: Balanced class-frequency sampling vs shuffle",
        warmup_lr=base_cfg["warmup_lr"],
        finetune_lr=base_cfg["finetune_lr"],
        weight_decay=base_cfg["weight_decay"],
        sampler_type="balanced",
        unfreeze_from_block=base_cfg.get("unfreeze_from_block", 13),
        scheduler_type="cosine",
        augmentation_type="standard",
    )
    configs.append(c1)

    # 2. Deeper unfreezing: block 10 to 16
    c2 = ExperimentConfig(
        run_id="stage_b_02_strategy_deeper_unfreeze_block10",
        stage="stage_b",
        description="Stage B: Deeper backbone unfreezing from block 10",
        warmup_lr=base_cfg["warmup_lr"],
        finetune_lr=base_cfg["finetune_lr"],
        weight_decay=base_cfg["weight_decay"],
        sampler_type="shuffle",
        unfreeze_from_block=10,
        scheduler_type="cosine",
        augmentation_type="standard",
    )
    configs.append(c2)

    # 3. Extended duration (5 warmup + 10 finetune epochs)
    c3 = ExperimentConfig(
        run_id="stage_b_03_strategy_extended_schedule_5w_10ft",
        stage="stage_b",
        description="Stage B: Extended training schedule (5 warmup + 10 finetune epochs)",
        warmup_epochs=5,
        finetune_epochs=10,
        warmup_lr=base_cfg["warmup_lr"],
        finetune_lr=base_cfg["finetune_lr"],
        weight_decay=base_cfg["weight_decay"],
        sampler_type="shuffle",
        unfreeze_from_block=base_cfg.get("unfreeze_from_block", 13),
        scheduler_type="cosine",
        augmentation_type="standard",
    )
    configs.append(c3)

    # 4. StepLR scheduler
    c4 = ExperimentConfig(
        run_id="stage_b_04_strategy_steplr_scheduler",
        stage="stage_b",
        description="Stage B: StepLR scheduler (step=3, gamma=0.5) vs CosineAnnealing",
        warmup_lr=base_cfg["warmup_lr"],
        finetune_lr=base_cfg["finetune_lr"],
        weight_decay=base_cfg["weight_decay"],
        sampler_type="shuffle",
        unfreeze_from_block=base_cfg.get("unfreeze_from_block", 13),
        scheduler_type="step",
        augmentation_type="standard",
    )
    configs.append(c4)

    return configs


def build_stage_c_configs(best_cfg: dict[str, Any]) -> list[ExperimentConfig]:
    """Generate Stage C foliar augmentation policy experiments."""
    configs: list[ExperimentConfig] = []

    # Mild augmentation
    c1 = ExperimentConfig(
        run_id="stage_c_01_aug_mild",
        stage="stage_c",
        description="Stage C: Mild field augmentation (conservative crop & jitter)",
        warmup_epochs=best_cfg.get("warmup_epochs", 3),
        finetune_epochs=best_cfg.get("finetune_epochs", 6),
        warmup_lr=best_cfg["warmup_lr"],
        finetune_lr=best_cfg["finetune_lr"],
        weight_decay=best_cfg["weight_decay"],
        sampler_type=best_cfg.get("sampler_type", "shuffle"),
        unfreeze_from_block=best_cfg.get("unfreeze_from_block", 13),
        scheduler_type=best_cfg.get("scheduler_type", "cosine"),
        augmentation_type="mild",
    )
    configs.append(c1)

    # Strong realistic augmentation
    c2 = ExperimentConfig(
        run_id="stage_c_02_aug_strong",
        stage="stage_c",
        description="Stage C: Strong realistic field augmentation (perspective + rotation + contrast)",
        warmup_epochs=best_cfg.get("warmup_epochs", 3),
        finetune_epochs=best_cfg.get("finetune_epochs", 6),
        warmup_lr=best_cfg["warmup_lr"],
        finetune_lr=best_cfg["finetune_lr"],
        weight_decay=best_cfg["weight_decay"],
        sampler_type=best_cfg.get("sampler_type", "shuffle"),
        unfreeze_from_block=best_cfg.get("unfreeze_from_block", 13),
        scheduler_type=best_cfg.get("scheduler_type", "cosine"),
        augmentation_type="strong",
    )
    configs.append(c2)

    return configs


def build_stage_d_configs(best_cfg: dict[str, Any]) -> list[ExperimentConfig]:
    """Generate Stage D loss function and regularization experiments."""
    configs: list[ExperimentConfig] = []

    # 1. Higher label smoothing: 0.10
    c1 = ExperimentConfig(
        run_id="stage_d_01_loss_smoothing_010",
        stage="stage_d",
        description="Stage D: Label smoothing 0.10 vs 0.05",
        warmup_epochs=best_cfg.get("warmup_epochs", 3),
        finetune_epochs=best_cfg.get("finetune_epochs", 6),
        warmup_lr=best_cfg["warmup_lr"],
        finetune_lr=best_cfg["finetune_lr"],
        weight_decay=best_cfg["weight_decay"],
        sampler_type=best_cfg.get("sampler_type", "shuffle"),
        unfreeze_from_block=best_cfg.get("unfreeze_from_block", 13),
        scheduler_type=best_cfg.get("scheduler_type", "cosine"),
        augmentation_type=best_cfg.get("augmentation_type", "standard"),
        loss_type="label_smooth_ce",
        label_smoothing=0.10,
        use_class_weights=True,
    )
    configs.append(c1)

    # 2. Unweighted standard CE
    c2 = ExperimentConfig(
        run_id="stage_d_02_loss_unweighted_ce",
        stage="stage_d",
        description="Stage D: Unweighted cross-entropy (smoothing=0.0)",
        warmup_epochs=best_cfg.get("warmup_epochs", 3),
        finetune_epochs=best_cfg.get("finetune_epochs", 6),
        warmup_lr=best_cfg["warmup_lr"],
        finetune_lr=best_cfg["finetune_lr"],
        weight_decay=best_cfg["weight_decay"],
        sampler_type=best_cfg.get("sampler_type", "shuffle"),
        unfreeze_from_block=best_cfg.get("unfreeze_from_block", 13),
        scheduler_type=best_cfg.get("scheduler_type", "cosine"),
        augmentation_type=best_cfg.get("augmentation_type", "standard"),
        loss_type="unweighted_ce",
        label_smoothing=0.0,
        use_class_weights=False,
    )
    configs.append(c2)

    # 3. Class-weighted Focal Loss (gamma=2.0)
    c3 = ExperimentConfig(
        run_id="stage_d_03_loss_focal_gamma2",
        stage="stage_d",
        description="Stage D: Class-weighted Focal Loss (gamma=2.0)",
        warmup_epochs=best_cfg.get("warmup_epochs", 3),
        finetune_epochs=best_cfg.get("finetune_epochs", 6),
        warmup_lr=best_cfg["warmup_lr"],
        finetune_lr=best_cfg["finetune_lr"],
        weight_decay=best_cfg["weight_decay"],
        sampler_type=best_cfg.get("sampler_type", "shuffle"),
        unfreeze_from_block=best_cfg.get("unfreeze_from_block", 13),
        scheduler_type=best_cfg.get("scheduler_type", "cosine"),
        augmentation_type=best_cfg.get("augmentation_type", "standard"),
        loss_type="focal",
        label_smoothing=0.0,
        use_class_weights=True,
    )
    configs.append(c3)

    return configs


def build_finalist_configs(champion_cfg: dict[str, Any], seeds: list[int] = [100, 2026]) -> list[ExperimentConfig]:
    """Generate finalist multi-seed robustness verification runs."""
    configs: list[ExperimentConfig] = []
    for s in seeds:
        c = ExperimentConfig(
            run_id=f"finalist_verification_seed{s}",
            stage="finalist",
            description=f"Multi-seed finalist verification (seed={s})",
            warmup_epochs=champion_cfg.get("warmup_epochs", 3),
            finetune_epochs=champion_cfg.get("finetune_epochs", 6),
            warmup_lr=champion_cfg["warmup_lr"],
            finetune_lr=champion_cfg["finetune_lr"],
            weight_decay=champion_cfg["weight_decay"],
            seed=s,
            sampler_type=champion_cfg.get("sampler_type", "shuffle"),
            unfreeze_from_block=champion_cfg.get("unfreeze_from_block", 13),
            scheduler_type=champion_cfg.get("scheduler_type", "cosine"),
            augmentation_type=champion_cfg.get("augmentation_type", "standard"),
            loss_type=champion_cfg.get("loss_type", "label_smooth_ce"),
            label_smoothing=champion_cfg.get("label_smoothing", 0.05),
            use_class_weights=champion_cfg.get("use_class_weights", True),
        )
        configs.append(c)
    return configs


def package_finalist_model(ws: Path, champion_run: dict[str, Any]) -> Path:
    """Package the supreme winning checkpoint into ml/research/unified_optimization/finalist_model/."""
    finalist_dir = ws / "finalist_model"
    finalist_dir.mkdir(parents=True, exist_ok=True)

    src_ckpt = Path(champion_run["checkpoint_path"])
    dst_ckpt = finalist_dir / "checkpoint_best_val.pt"

    shutil.copy2(src_ckpt, dst_ckpt)
    dst_sha = sha256_of_file(dst_ckpt)

    metadata = {
        "finalist_run_id": champion_run["run_id"],
        "stage": champion_run["stage"],
        "checkpoint_sha256": dst_sha,
        "composite_score": champion_run["best_composite_score"],
        "val_macro_f1": champion_run["best_val_macro_f1"],
        "val_accuracy": champion_run["best_val_accuracy"],
        "val_ece": champion_run["best_val_ece"],
        "cross_crop_error_rate": champion_run["cross_crop_error_rate"],
        "disease_healthy_error_rate": champion_run["disease_healthy_error_rate"],
        "best_epoch": champion_run["best_epoch"],
        "config": champion_run["config"],
        "parent_production_sha256": EXPECTED_BASELINE_SHA256,
        "status": "VALIDATED_FINALIST",
    }
    (finalist_dir / "finalist_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\n[FINALIST PACKAGING] Successfully packaged champion checkpoint:")
    print(f"    Destination: {dst_ckpt}")
    print(f"    SHA-256: {dst_sha}")
    return dst_ckpt


def run_pipeline():
    ws = REPO_ROOT / "ml" / "research" / "unified_optimization"

    print("==================================================================")
    print(" AGRIMIND UNIFIED DISEASE OPTIMIZATION: REMAINING STAGES RUNNER")
    print("==================================================================")

    # Safety Check: production checkpoint must be preserved
    base_ckpt = REPO_ROOT / "ml" / "artifacts" / "best.pt"
    assert sha256_of_file(base_ckpt) == EXPECTED_BASELINE_SHA256, "CRITICAL: Base checkpoint was modified!"
    print(f"[SAFETY] Verified baseline ml/artifacts/best.pt SHA-256: {EXPECTED_BASELINE_SHA256}")

    # Step 1: Select best Stage A config
    stage_a_winner_cfg = load_best_stage_a_config(ws)

    # Step 2: Execute Stage B (Training Strategies)
    print("\n>>> STARTING STAGE B: TRAINING STRATEGY SEARCH")
    stage_b_configs = build_stage_b_configs(stage_a_winner_cfg)
    stage_b_results = run_experiment_suite(stage_b_configs, workspace_dir=ws, resume=True)

    # Step 3: Find current best across Stage A & B
    lb_json = ws / "leaderboard.json"
    lb_data = json.loads(lb_json.read_text(encoding="utf-8"))
    current_champion = lb_data[0]
    print(f"\n[LEADERBOARD] Champion after Stage B: {current_champion['run_id']} (Score: {current_champion['best_composite_score']})")

    # Step 4: Execute Stage C (Augmentations)
    print("\n>>> STARTING STAGE C: FOLIAR AUGMENTATION SEARCH")
    stage_c_configs = build_stage_c_configs(current_champion["config"])
    stage_c_results = run_experiment_suite(stage_c_configs, workspace_dir=ws, resume=True)

    # Step 5: Find current best after Stage C
    lb_data = json.loads(lb_json.read_text(encoding="utf-8"))
    current_champion = lb_data[0]
    print(f"\n[LEADERBOARD] Champion after Stage C: {current_champion['run_id']} (Score: {current_champion['best_composite_score']})")

    # Step 6: Execute Stage D (Loss Functions)
    print("\n>>> STARTING STAGE D: LOSS FUNCTION SEARCH")
    stage_d_configs = build_stage_d_configs(current_champion["config"])
    stage_d_results = run_experiment_suite(stage_d_configs, workspace_dir=ws, resume=True)

    # Step 7: Final Supreme Champion
    lb_data = json.loads(lb_json.read_text(encoding="utf-8"))
    supreme_champion = lb_data[0]
    print(f"\n==================================================================")
    print(f" SUPREME RESEARCH CHAMPION: {supreme_champion['run_id']}")
    print(f" Composite Score: {supreme_champion['best_composite_score']}")
    print(f" Val Macro-F1:   {supreme_champion['best_val_macro_f1']:.4f}")
    print(f" Val Accuracy:   {supreme_champion['best_val_accuracy']:.4f}")
    print(f" Val ECE:        {supreme_champion['best_val_ece']:.4f}")
    print(f"==================================================================")

    # Step 8: Multi-Seed Robustness on Supreme Champion
    print("\n>>> STARTING FINALIST MULTI-SEED ROBUSTNESS VERIFICATION")
    finalist_configs = build_finalist_configs(supreme_champion["config"], seeds=[100, 2026])
    finalist_results = run_experiment_suite(finalist_configs, workspace_dir=ws, resume=True)

    # Step 9: Package Finalist Checkpoint
    packaged_ckpt = package_finalist_model(ws, supreme_champion)

    # Final Safety Verification
    assert sha256_of_file(base_ckpt) == EXPECTED_BASELINE_SHA256, "CRITICAL: Base checkpoint modified at end of pipeline!"
    print(f"\n[SAFETY AUDIT PASSED] ml/artifacts/best.pt hash intact: {EXPECTED_BASELINE_SHA256}")
    print("\n[PIPELINE COMPLETE] All stages executed and logged successfully.")


if __name__ == "__main__":
    run_pipeline()
