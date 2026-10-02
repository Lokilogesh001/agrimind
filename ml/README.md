# Disease model

AgriMind uses a MobileNetV3-Large image classifier for crop disease identification across 38 PlantVillage classes.
The active inference checkpoint is stored at `ml/artifacts/best.pt`.

Training pipeline CLI:

```bash
python -m ml.train_disease \
  --root /path/to/PlantVillage \
  --train-manifest /path/to/splits/color_train.txt \
  --test-manifest /path/to/splits/color_test.txt \
  --epochs 15 --batch-size 64 --num-workers 2 \
  --output ml/artifacts/best.pt
```

The PlantVillage dataset provides disease-classification labels; **severity is not learned from it**. The Disease Agent uses an agronomic keyword heuristic on the predicted disease component (`blight`, `rot`, `wilt`, `rust`, etc.) to determine urgency until a calibrated severity dataset is introduced. Disease labels are automatically normalized (e.g., `Tomato___Early_blight` → `early blight`) for high-fidelity ICAR knowledge retrieval.
