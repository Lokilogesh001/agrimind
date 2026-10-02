"""PlantVillage manifest-backed PyTorch dataset.

Supports the official Hugging Face PlantVillage split manifests, e.g.
``splits/color_train.txt`` and ``splits/color_test.txt``.  The manifests contain
paths such as ``raw/color/Tomato___Early_blight/file.JPG``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image
from torch.utils.data import Dataset


class PlantVillageManifestDataset(Dataset):
    def __init__(
        self,
        root: str | Path,
        manifest: str | Path,
        transform=None,
        class_to_idx: dict[str, int] | None = None,
    ) -> None:
        self.root = Path(root)
        self.manifest = Path(manifest)
        self.transform = transform
        entries = [
            line.strip() for line in self.manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.entries = entries
        self.labels = [self._class_name(e) for e in entries]
        classes = sorted(set(self.labels))
        self.class_to_idx = class_to_idx or {name: i for i, name in enumerate(classes)}
        missing = [e for e in entries if not self._path(e).is_file()]
        if missing:
            raise FileNotFoundError(
                f"{len(missing)} manifest images are missing under {self.root}. "
                f"First missing path: {missing[0]}"
            )
        unknown = sorted(set(self.labels) - set(self.class_to_idx))
        if unknown:
            raise ValueError(f"Unknown classes in manifest: {unknown}")

    @staticmethod
    def _class_name(entry: str) -> str:
        parts = entry.replace("\\", "/").split("/")
        try:
            return parts[parts.index("color") + 1]
        except ValueError:
            for part in parts:
                if "___" in part:
                    return part
        raise ValueError(f"Cannot infer PlantVillage class from: {entry}")

    def _path(self, entry: str) -> Path:
        return self.root / entry

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int):
        entry = self.entries[index]
        image = Image.open(self._path(entry)).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, self.class_to_idx[self.labels[index]]

    @property
    def classes(self) -> list[str]:
        return [name for name, _ in sorted(self.class_to_idx.items(), key=lambda x: x[1])]
