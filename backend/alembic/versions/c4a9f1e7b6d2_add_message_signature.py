"""add message signature and sent_at

Revision ID: c4a9f1e7b6d2
Revises: 9c3d2e1f0a4b
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a9f1e7b6d2"
down_revision: str | None = "9c3d2e1f0a4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Issue #59: EIP-191 signature and the exact client timestamp it covers.
    # Both nullable so legacy messages stay valid and render as unverified.
    op.add_column(
        "message",
        sa.Column("signature", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "message",
        sa.Column("sent_at", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("message", "sent_at")
    op.drop_column("message", "signature")
