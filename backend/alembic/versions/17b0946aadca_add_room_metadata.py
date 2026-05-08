"""add room metadata

Revision ID: 17b0946aadca
Revises: a1b2c3d4e5f6
Create Date: 2026-05-08 13:33:01.114422

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17b0946aadca"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "room",
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "room",
        sa.Column(
            "communicator_link",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "room",
        sa.Column(
            "requirements",
            sqlmodel.sql.sqltypes.AutoString(length=1000),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("room", "requirements")
    op.drop_column("room", "communicator_link")
    op.drop_column("room", "description")
