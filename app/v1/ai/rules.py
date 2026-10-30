"""Central safety rule engine: COMPLIANT / VIOLATION / UNKNOWN."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleDecision:
    primary_violation: Optional[str]
    status: str  # compliant | warning | violation
    helmet_status: str
    vest_status: str
    pose_status: str
    is_fallen: bool


def evaluate_worker(
    *,
    helmet_status: str,
    vest_status: str,
    is_fallen: bool,
    pose_status: str = "unknown",
    zone_name: Optional[str] = None,
) -> RuleDecision:
    """
    Priority: fall → zone → helmet → vest.
    UNKNOWN PPE never becomes a violation by itself and never counts as compliant display OK.
    """
    primary = None
    if is_fallen or pose_status == "fall_transition":
        primary = "WORKER_FALL_DETECTED"
        status = "violation"
    elif zone_name:
        primary = "ZONE_INTRUSION"
        status = "violation"
    elif helmet_status == "violation":
        primary = "NO_HELMET"
        status = "warning"
    elif vest_status == "violation":
        primary = "NO_VEST"
        status = "warning"
    else:
        status = "compliant"
        if helmet_status == "unknown" or vest_status == "unknown":
            status = "warning" if status == "compliant" else status

    # Display status: unknown PPE should not show as fully compliant
    if primary is None and (helmet_status == "unknown" or vest_status == "unknown"):
        status = "warning"

    return RuleDecision(
        primary_violation=primary,
        status=status,
        helmet_status=helmet_status,
        vest_status=vest_status,
        pose_status=pose_status,
        is_fallen=is_fallen or pose_status == "fall_transition",
    )


def status_to_bool_compliant(status: str) -> bool:
    """Backward-compat: only True when explicitly compliant."""
    return status == "compliant"
