"""Runnable check for safety rule engine. python -m app.v1.ai.self_check_rules"""

from app.v1.ai.rules import evaluate_worker, status_to_bool_compliant


def main() -> None:
    fall = evaluate_worker(helmet_status="compliant", vest_status="compliant", is_fallen=True)
    assert fall.primary_violation == "WORKER_FALL_DETECTED"
    assert fall.status == "violation"

    no_helmet = evaluate_worker(
        helmet_status="violation", vest_status="compliant", is_fallen=False
    )
    assert no_helmet.primary_violation == "NO_HELMET"

    unknown = evaluate_worker(
        helmet_status="unknown", vest_status="unknown", is_fallen=False
    )
    assert unknown.primary_violation is None
    assert unknown.status == "warning"
    assert status_to_bool_compliant("unknown") is False
    assert status_to_bool_compliant("compliant") is True

    zone = evaluate_worker(
        helmet_status="compliant",
        vest_status="compliant",
        is_fallen=False,
        zone_name="Restricted",
    )
    assert zone.primary_violation == "ZONE_INTRUSION"
    print("self_check_rules: OK")


if __name__ == "__main__":
    main()
