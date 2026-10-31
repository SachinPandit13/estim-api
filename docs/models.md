# Estim AI Model Inventory

Single-org industrial safety. Tracking IDs are camera-local temporary identities, not employees.

## Active models

| Slot | Architecture | Weights | Classes | Status |
|------|--------------|---------|---------|--------|
| Person | YOLOv8n COCO | `yolov8n.pt` (`PERSON_MODEL_PATH`) | `person` (class 0) | **Enabled** |
| PPE | Dedicated YOLO (slot) | `PPE_MODEL_PATH` | Must verify from weight `names` (helmet/vest/head…) | **Disabled until evaluated** |
| Fire/Smoke | Dedicated YOLO (slot) | `FIRE_SMOKE_MODEL_PATH` | Must verify (`fire`/`smoke`/…) | **Disabled until evaluated** |
| Pose/Fall | YOLO-Pose (slot) | `POSE_MODEL_PATH` | COCO keypoints | **Disabled until evaluated** |

Bridge heuristics (not production claims):

- PPE: RGB crown/torso color ratios → `compliant` / `violation` / `unknown` (never fail-open to compliant).
- Fall: bbox aspect prefilter; pose rules when pose weights load.

## Runtime

- Device: `AI_DEVICE=auto|cpu|cuda` (this workstation is CPU-first).
- Sample rate: `FRAME_SAMPLE_RATE` (default 2 Hz).
- Cadence: `PPE_CADENCE`, `FIRE_SMOKE_CADENCE`, `POSE_CADENCE`.
- Enable flags: `ENABLE_PPE_MODEL`, `ENABLE_FIRE_SMOKE_MODEL`, `ENABLE_POSE_FALL_MODEL`.

## Evaluation gate (Phase 2)

Do **not** enable specialty models in production until site CCTV eval notes exist:

1. Collect representative frames (angles, lighting, occlusion, distant workers).
2. Include hard negatives: welding sparks, lights, sun, orange objects, steam/dust/fog.
3. Measure precision/recall **separately** for fire vs smoke; helmet vs vest.
4. Record exact class names from `model.names` — never assume.
5. Only then set path + `ENABLE_*=true`.

## Custom training (Phase 3)

If public weights fail site eval:

- Positive + negative industrial examples; varied PPE colors/designs.
- Split by recording/session — **no** adjacent-frame train/test leak.
- Export Ultralytics `.pt` into registry paths above.
- Optional BoT-SORT only after measured ID-switch pain; ONNX/TensorRT only after FPS profiling.

## License

`yolov8n.pt` follows Ultralytics / AGPL-compatible terms for the Ultralytics package in use. Third-party PPE/fire weights: record license before shipping.
