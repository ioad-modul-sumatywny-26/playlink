"""initial tables

Revision ID: 001
Revises:
Create Date: 2026-04-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # These tables may already exist on production (created via create_all)
    if "user" not in existing_tables:
        op.create_table(
            "user",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("identity_address", sa.String(), nullable=False),
            sa.Column("username", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_user_identity_address", "user", ["identity_address"], unique=True
        )
        op.create_index("ix_user_username", "user", ["username"], unique=True)

    if "nonce" not in existing_tables:
        op.create_table(
            "nonce",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("identity_address", sa.String(), nullable=False),
            sa.Column("value", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("value"),
        )
        op.create_index(
            "ix_nonce_identity_address", "nonce", ["identity_address"], unique=False
        )

    # room is always new
    if "room" not in existing_tables:
        op.create_table(
            "room",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("game", sa.String(), nullable=False),
            sa.Column("players_max", sa.Integer(), nullable=False),
            sa.Column("players_active", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_room_name", "room", ["name"], unique=True)
        op.create_index("ix_room_created_by", "room", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_table("room")
    op.drop_index("ix_nonce_identity_address", table_name="nonce")
    op.drop_table("nonce")
    op.drop_index("ix_user_identity_address", table_name="user")
    op.drop_index("ix_user_username", table_name="user")
    op.drop_table("user")
