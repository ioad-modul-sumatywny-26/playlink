"""add room lobby location

Revision ID: 9c3d2e1f0a4b
Revises: b7e2c1f4d8a3
Create Date: 2026-06-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c3d2e1f0a4b"
down_revision: str | None = "b7e2c1f4d8a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_LOBBY_LOCATION = "eu-central"


def upgrade() -> None:
    op.add_column(
        "room",
        sa.Column(
            "lobby_location",
            sa.String(),
            nullable=False,
            server_default=DEFAULT_LOBBY_LOCATION,
        ),
    )
    op.create_index(
        op.f("ix_room_lobby_location"), "room", ["lobby_location"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_room_lobby_location"), table_name="room")
    op.drop_column("room", "lobby_location")
