"""create_table_detection_events

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-10-27 18:12:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a1b2"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "detection_events",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column(
            "camera_id",
            sa.String(),
            sa.ForeignKey("cameras.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("snapshot_url", sa.String(length=1024), nullable=True),
        sa.Column("video_clip_url", sa.String(length=1024), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            default=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_detection_events_id", "detection_events", ["id"], unique=True)
    op.create_index(
        "ix_detection_events_camera_id", "detection_events", ["camera_id"]
    )
    op.create_index(
        "ix_detection_events_event_type", "detection_events", ["event_type"]
    )
    op.create_index(
        "ix_detection_events_detected_at", "detection_events", ["detected_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_detection_events_detected_at", "detection_events")
    op.drop_index("ix_detection_events_event_type", "detection_events")
    op.drop_index("ix_detection_events_camera_id", "detection_events")
    op.drop_index("ix_detection_events_id", "detection_events")
    op.drop_table("detection_events")
