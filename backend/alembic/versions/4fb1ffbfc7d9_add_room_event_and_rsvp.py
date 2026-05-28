"""add room event and rsvp

Revision ID: 4fb1ffbfc7d9
Revises: 17b0946aadca
Create Date: 2026-05-27 22:14:41.377640

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4fb1ffbfc7d9"
down_revision: str | None = "17b0946aadca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roomevent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["room.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_roomevent_created_by"), "roomevent", ["created_by"], unique=False
    )
    op.create_index(op.f("ix_roomevent_room_id"), "roomevent", ["room_id"], unique=True)
    op.create_index(
        op.f("ix_roomevent_starts_at"), "roomevent", ["starts_at"], unique=False
    )

    op.create_table(
        "roomeventrsvp",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("present", "absent", "maybe", name="rsvpstatus"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["roomevent.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id"),
    )
    op.create_index(
        op.f("ix_roomeventrsvp_event_id"),
        "roomeventrsvp",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_roomeventrsvp_user_id"),
        "roomeventrsvp",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_roomeventrsvp_user_id"), table_name="roomeventrsvp")
    op.drop_index(op.f("ix_roomeventrsvp_event_id"), table_name="roomeventrsvp")
    op.drop_table("roomeventrsvp")
    # Drop the named ENUM type explicitly (Postgres keeps it after drop_table;
    # SQLite ignores this no-op).
    sa.Enum(name="rsvpstatus").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_roomevent_starts_at"), table_name="roomevent")
    op.drop_index(op.f("ix_roomevent_room_id"), table_name="roomevent")
    op.drop_index(op.f("ix_roomevent_created_by"), table_name="roomevent")
    op.drop_table("roomevent")
