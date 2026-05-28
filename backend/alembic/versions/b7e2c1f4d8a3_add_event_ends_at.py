"""add ends_at to room event

Revision ID: b7e2c1f4d8a3
Revises: 4fb1ffbfc7d9
Create Date: 2026-05-27 23:50:00.000000

"""

from collections.abc import Sequence
from datetime import timedelta

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2c1f4d8a3"
down_revision: str | None = "4fb1ffbfc7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add the column nullable so we can backfill existing rows, then enforce
    # NOT NULL. New rows always provide ends_at via the API, so this is only
    # relevant if some env already has events from the prior migration.
    op.add_column(
        "roomevent",
        sa.Column("ends_at", sa.DateTime(), nullable=True),
    )

    # Backfill: assume any existing event lasts 2 hours by default.
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, starts_at FROM roomevent")).fetchall()
    for row_id, starts_at in rows:
        bind.execute(
            sa.text("UPDATE roomevent SET ends_at = :ends WHERE id = :id"),
            {"ends": starts_at + timedelta(hours=2), "id": row_id},
        )

    # Tighten to NOT NULL. SQLite needs batch_alter_table (it rebuilds the
    # table); Postgres handles a plain ALTER COLUMN.
    with op.batch_alter_table("roomevent") as batch_op:
        batch_op.alter_column("ends_at", existing_type=sa.DateTime(), nullable=False)

    op.create_index(
        op.f("ix_roomevent_ends_at"), "roomevent", ["ends_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_roomevent_ends_at"), table_name="roomevent")
    op.drop_column("roomevent", "ends_at")
