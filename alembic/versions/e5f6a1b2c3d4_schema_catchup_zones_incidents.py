"""schema catch-up: camera columns, zones, incidents, detection/notification columns

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-10-30 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    # cameras drifted columns
    if _has_table("cameras"):
        if not _has_column("cameras", "description"):
            op.add_column("cameras", sa.Column("description", sa.String(length=500), nullable=True))
        if not _has_column("cameras", "source_type"):
            op.add_column(
                "cameras",
                sa.Column("source_type", sa.String(length=50), nullable=False, server_default="rtsp"),
            )
        if not _has_column("cameras", "rtsp_username"):
            op.add_column("cameras", sa.Column("rtsp_username", sa.String(length=255), nullable=True))
        if not _has_column("cameras", "rtsp_password"):
            op.add_column("cameras", sa.Column("rtsp_password", sa.String(length=255), nullable=True))
        if not _has_column("cameras", "dvr_channel"):
            op.add_column("cameras", sa.Column("dvr_channel", sa.Integer(), nullable=True))
        if not _has_column("cameras", "is_enabled"):
            op.add_column(
                "cameras",
                sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            )
        if not _has_column("cameras", "last_connected_at"):
            op.add_column("cameras", sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("cameras", "last_error"):
            op.add_column("cameras", sa.Column("last_error", sa.String(length=1000), nullable=True))

    # users.hashed_password
    if _has_table("users") and not _has_column("users", "hashed_password"):
        op.add_column("users", sa.Column("hashed_password", sa.String(length=255), nullable=True))

    # camera_zones
    if not _has_table("camera_zones"):
        op.create_table(
            "camera_zones",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("camera_id", sa.String(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("roi_polygon", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_camera_zones_id", "camera_zones", ["id"])
        op.create_index("ix_camera_zones_camera_id", "camera_zones", ["camera_id"])

    # detection_events columns
    if _has_table("detection_events"):
        if not _has_column("detection_events", "zone_id"):
            op.add_column(
                "detection_events",
                sa.Column("zone_id", sa.String(), sa.ForeignKey("camera_zones.id", ondelete="SET NULL"), nullable=True),
            )
            op.create_index("ix_detection_events_zone_id", "detection_events", ["zone_id"])
        if not _has_column("detection_events", "bounding_box"):
            op.add_column("detection_events", sa.Column("bounding_box", sa.JSON(), nullable=True))

    # safety_incidents
    if not _has_table("safety_incidents"):
        op.create_table(
            "safety_incidents",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("incident_type", sa.String(length=100), nullable=False),
            sa.Column("severity", sa.String(length=50), nullable=False, server_default="medium"),
            sa.Column("camera_id", sa.String(), sa.ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True),
            sa.Column("zone_id", sa.String(), sa.ForeignKey("camera_zones.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
            sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("detection_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("evidence_snapshot", sa.String(length=1024), nullable=True),
            sa.Column("assigned_to_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_safety_incidents_id", "safety_incidents", ["id"])
        op.create_index("ix_safety_incidents_incident_type", "safety_incidents", ["incident_type"])
        op.create_index("ix_safety_incidents_severity", "safety_incidents", ["severity"])
        op.create_index("ix_safety_incidents_camera_id", "safety_incidents", ["camera_id"])
        op.create_index("ix_safety_incidents_status", "safety_incidents", ["status"])
        op.create_index("ix_safety_incidents_first_detected_at", "safety_incidents", ["first_detected_at"])

    # notifications.incident_id + camera_id index
    if _has_table("notifications") and not _has_column("notifications", "incident_id"):
        op.add_column(
            "notifications",
            sa.Column(
                "incident_id",
                sa.String(),
                sa.ForeignKey("safety_incidents.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_notifications_incident_id", "notifications", ["incident_id"])


def downgrade() -> None:
    # Non-destructive downgrade omitted for catch-up migration safety
    pass
