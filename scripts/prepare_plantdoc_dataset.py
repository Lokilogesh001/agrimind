"""PlantDoc Independent Test Dataset Preparation Utility for AgriMind.

Extracts, validates, hashes, and maps the PlantDoc test set (Singh et al., ACM CoDS-COMAD 2020)
under CC BY 4.0 license to AgriMind's 38-class MobileNetV3-Large disease classifier taxonomy.

Outputs:
- Verified images in evaluation/datasets/plantdoc_test/images/
- Auditable manifest in evaluation/manifests/plantdoc_test_manifest.csv
- Template manifest in evaluation/manifests/external_test_manifest_template.csv
- Dataset provenance and summary report
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from PIL import Image


PLANTDOC_TO_PLANTVILLAGE: dict[str, str] = {
    "Apple Scab Leaf": "Apple___Apple_scab",
    "Apple leaf": "Apple___healthy",
    "Apple rust leaf": "Apple___Cedar_apple_rust",
    "Bell_pepper leaf": "Pepper,_bell___healthy",
    "Bell_pepper leaf spot": "Pepper,_bell___Bacterial_spot",
    "Blueberry leaf": "Blueberry___healthy",
    "Cherry leaf": "Cherry_(including_sour)___healthy",
    "Corn Gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn leaf blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Corn rust leaf": "Corn_(maize)___Common_rust_",
    "Peach leaf": "Peach___healthy",
    "Potato leaf early blight": "Potato___Early_blight",
    "Potato leaf late blight": "Potato___Late_blight",
    "Raspberry leaf": "Raspberry___healthy",
    "Soyabean leaf": "Soybean___healthy",
    "Squash Powdery mildew leaf": "Squash___Powdery_mildew",
    "Strawberry leaf": "Strawberry___healthy",
    "Tomato Early blight leaf": "Tomato___Early_blight",
    "Tomato Septoria leaf spot": "Tomato___Septoria_leaf_spot",
    "Tomato leaf": "Tomato___healthy",
    "Tomato leaf bacterial spot": "Tomato___Bacterial_spot",
    "Tomato leaf late blight": "Tomato___Late_blight",
    "Tomato leaf mosaic virus": "Tomato___Tomato_mosaic_virus",
    "Tomato leaf yellow virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato mold leaf": "Tomato___Leaf_Mold",
    "grape leaf": "Grape___healthy",
    "grape leaf black rot": "Grape___Black_rot",
}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for Windows NTFS and POSIX cross-compatibility."""
    # Replace illegal Windows characters: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", filename)
    # Remove leading/trailing spaces or dots
    cleaned = cleaned.strip(". ")
    return cleaned or "unnamed_image.jpg"


def extract_plantdoc_from_git(
    repo_path: Path,
    output_dir: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Extract and validate PlantDoc test images directly from git repository tree."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "-C", str(repo_path), "ls-tree", "-r", "HEAD", "test/"]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
        lines = proc.stdout.decode("utf-8", errors="replace").splitlines()
    except Exception as exc:
        raise RuntimeError(f"Failed to read git tree from {repo_path}: {exc}") from exc

    manifest_rows: list[dict[str, Any]] = []
    seen_hashes: dict[str, str] = {}
    duplicates: list[dict[str, str]] = []
    corrupted: list[str] = []
    class_counts: dict[str, int] = {}

    for line in lines:
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        meta, git_rel_path = parts[0], parts[1]
        blob_hash = meta.split()[2]

        path_elements = git_rel_path.split("/")
        if len(path_elements) < 3:
            continue
        folder_label = path_elements[1]
        raw_filename = path_elements[2]

        clean_folder = sanitize_filename(folder_label)
        clean_file = sanitize_filename(raw_filename)

        # Retrieve binary blob from git object store
        blob_cmd = ["git", "-C", str(repo_path), "cat-file", "blob", blob_hash]
        blob_data = subprocess.run(blob_cmd, capture_output=True, check=True).stdout

        sha256_digest = hashlib.sha256(blob_data).hexdigest()

        # Check duplicate
        if sha256_digest in seen_hashes:
            duplicates.append({
                "duplicate_path": git_rel_path,
                "first_seen_path": seen_hashes[sha256_digest],
                "sha256": sha256_digest,
            })
        else:
            seen_hashes[sha256_digest] = git_rel_path

        # Verify image integrity
        try:
            with Image.open(io.BytesIO(blob_data)) as img:
                img.verify()
                format_detected = img.format
        except Exception as exc:
            corrupted.append(f"{git_rel_path}: {exc}")
            continue

        # Save to disk
        target_folder = output_dir / clean_folder
        target_folder.mkdir(parents=True, exist_ok=True)
        dest_file = target_folder / clean_file
        dest_file.write_bytes(blob_data)

        mapped_class = PLANTDOC_TO_PLANTVILLAGE.get(folder_label, "UNMAPPED")
        rel_saved_path = f"{clean_folder}/{clean_file}"

        # Assign a grouped specimen ID based on filename stem or original capture
        stem = Path(clean_file).stem
        group_id = stem.split("_")[0] if "_" in stem else stem

        manifest_rows.append({
            "image_path": rel_saved_path,
            "original_label": folder_label,
            "mapped_class": mapped_class,
            "source_dataset": "PlantDoc",
            "provenance": "Singh et al., ACM CoDS-COMAD 2020 (CC BY 4.0)",
            "capture_setting": "Non-laboratory field photography with complex natural clutter",
            "group_id": group_id,
            "sha256": sha256_digest,
            "file_size_bytes": len(blob_data),
        })

        class_counts[mapped_class] = class_counts.get(mapped_class, 0) + 1

    # Write manifest CSV
    fieldnames = [
        "image_path",
        "original_label",
        "mapped_class",
        "source_dataset",
        "provenance",
        "capture_setting",
        "group_id",
        "sha256",
        "file_size_bytes",
    ]
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    summary = {
        "dataset_name": "PlantDoc Test Dataset",
        "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "source_citation": "Singh et al., 'PlantDoc: A Dataset for Collaborative Computer Vision in Agriculture', ACM CoDS-COMAD 2020",
        "total_images_processed": len(lines),
        "total_valid_images": len(manifest_rows),
        "corrupted_images_count": len(corrupted),
        "exact_duplicates_count": len(duplicates),
        "unique_images_count": len(seen_hashes),
        "mapped_classes_count": len([c for c in class_counts if c != "UNMAPPED"]),
        "unmapped_classes_count": len([c for c in class_counts if c == "UNMAPPED"]),
        "per_class_support": class_counts,
        "manifest_path": str(manifest_path),
        "images_directory": str(output_dir),
    }

    return summary


def write_template_manifest(template_path: Path) -> None:
    """Generate a template manifest for external agronomist and field validation datasets."""
    template_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image_path",
        "original_label",
        "mapped_class",
        "source_dataset",
        "provenance",
        "capture_setting",
        "group_id",
        "sha256",
        "file_size_bytes",
    ]
    rows = [
        {
            "image_path": "field_batch_01/tomato_sample_001.jpg",
            "original_label": "Tomato Early Blight",
            "mapped_class": "Tomato___Early_blight",
            "source_dataset": "KVK_Field_Trial_2026",
            "provenance": "ICAR-KVK Baramati, Pune District, Maharashtra",
            "capture_setting": "Open-field canopy, natural daylight, unwashed foliage",
            "group_id": "plot_4_plant_12",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "file_size_bytes": 1048576,
        },
        {
            "image_path": "field_batch_01/corn_sample_002.jpg",
            "original_label": "Corn Common Rust",
            "mapped_class": "Corn_(maize)___Common_rust_",
            "source_dataset": "KVK_Field_Trial_2026",
            "provenance": "ICAR-KVK Baramati, Pune District, Maharashtra",
            "capture_setting": "Open-field canopy, overcast, mid-growth stage",
            "group_id": "plot_2_plant_05",
            "sha256": "f4c0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b999",
            "file_size_bytes": 1245820,
        },
    ]
    with open(template_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Prepare PlantDoc test dataset and manifest")
    parser.add_argument(
        "--repo-path",
        default="evaluation/datasets/plantdoc_repo",
        help="Path to cloned PlantDoc git repository",
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation/datasets/plantdoc_test/images",
        help="Path to save validated test images",
    )
    parser.add_argument(
        "--manifest-path",
        default="evaluation/manifests/plantdoc_test_manifest.csv",
        help="Path to output manifest CSV",
    )
    parser.add_argument(
        "--template-path",
        default="evaluation/manifests/external_test_manifest_template.csv",
        help="Path to output template manifest CSV",
    )
    args = parser.parse_args()

    repo_dir = Path(args.repo_path)
    out_dir = Path(args.output_dir)
    manifest = Path(args.manifest_path)
    template = Path(args.template_path)

    print(f"[PREPARE] Processing PlantDoc dataset from {repo_dir}...")
    summary = extract_plantdoc_from_git(repo_dir, out_dir, manifest)
    write_template_manifest(template)

    print(f"[PREPARE] Extraction complete!")
    print(f"  Valid images: {summary['total_valid_images']}")
    print(f"  Mapped classes: {summary['mapped_classes_count']}")
    print(f"  Exact duplicates detected: {summary['exact_duplicates_count']}")
    print(f"  Corrupted images: {summary['corrupted_images_count']}")
    print(f"  Manifest saved to: {manifest}")
    print(f"  Template saved to: {template}")


if __name__ == "__main__":
    main()
