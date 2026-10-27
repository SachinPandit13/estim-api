"""create_table_users

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-10-27 18:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "role", sa.String(length=50), nullable=False, server_default="member"
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            default=True,
            server_default=sa.text("true"),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_users_id", "users", ["id"], unique=True)
    op.create_index("ix_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_id", "users")
    op.drop_table("users")
