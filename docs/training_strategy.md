# Custom training strategy (Phase 3)

Only after Phase 2 eval rejects public weights.

## Datasets

1. **PPE:** Helmet / No-Helmet / Vest / No-Vest (+ Person/Head if useful). Include site hardhats of multiple colors, hi-vis designs, occlusion, night IR if used.
2. **Fire/Smoke:** Flames and smoke plumes plus hard negatives (welding, lights, sun, orange objects, steam, dust, fog).
3. **Pose/Fall (optional fine-tune):** Prefer rule engine on COCO pose first; fine-tune only if site fall poses are systematically missed.

## Split policy

- Group by **recording session / camera / day**.
- Never put adjacent frames from the same clip into both train and test.
- Target ~70/15/15 train/val/test by session groups.

## Training notes

- Start from Ultralytics YOLO nano/small for CPU deployment.
- imgsz 640; augment: mosaic, HSV, flip; avoid over-augment that invents impossible PPE.
- Export `.pt` to paths referenced by Settings; document `names` in `docs/models.md`.
- Gate enable flags on val metrics + site smoke test.

## Tracker upgrade path

`ponytail: ByteTrack until ID-switch measured` — switch to BoT-SORT+ReID only with footage proving ID thrash.
