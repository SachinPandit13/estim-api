# Specialty model evaluation checklist

Use before setting `ENABLE_PPE_MODEL` / `ENABLE_FIRE_SMOKE_MODEL` / `ENABLE_POSE_FALL_MODEL`.

## PPE candidate weight

- [ ] Weight path recorded in `PPE_MODEL_PATH`
- [ ] Printed `model.names` and mapped to helmet/vest/head/no-* classes
- [ ] Precision/recall on held-out site cameras (not adjacent frames)
- [ ] Association IoU with head/torso ROIs checked for overlapping workers
- [ ] UNKNOWN rate acceptable on occluded / distant workers
- [ ] Decision: enable / reject / custom-train

## Fire/smoke candidate weight

- [ ] Weight path recorded
- [ ] Classes mapped to FIRE_DETECTED / SMOKE_DETECTED
- [ ] Negatives tested: welding, lights, sun glare, orange PPE, reflections, steam, dust
- [ ] Fire vs smoke metrics separate
- [ ] Temporal confirmation frames calibrated
- [ ] Decision: enable / reject / custom-train

## Pose/fall candidate weight

- [ ] YOLO-Pose weight loads on CPU target hardware
- [ ] Fall transition vs sitting/bending/kneeling false-positive review
- [ ] One incident per track_id confirmed fall
- [ ] Decision: enable / keep bbox prefilter bridge

## Notes

Site: _______________ Date: _______________ Reviewer: _______________
