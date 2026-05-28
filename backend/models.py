import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class RoomMember(SQLModel, table=True):
    room_id: int = Field(default=None, foreign_key="room.id", primary_key=True)
    user_id: int = Field(default=None, foreign_key="user.id", primary_key=True)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Room(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    game: str
    players_max: int
    description: str | None = Field(default=None, max_length=500)
    communicator_link: str | None = Field(default=None, max_length=500)
    requirements: str | None = Field(default=None, max_length=1000)
    created_by: str = Field(index=True)  # identity_address of creator
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC) + timedelta(minutes=60)
    )

    members: list[User] = Relationship(back_populates="rooms", link_model=RoomMember)


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="room.id", index=True)
    sender_address: str = Field(index=True)
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class RsvpStatus(StrEnum):
    """Attendance state a member can advertise for a scheduled RoomEvent."""

    present = "present"
    absent = "absent"
    maybe = "maybe"


class RoomEvent(SQLModel, table=True):
    """A single scheduled gathering attached to a Room.

    Issue #62 only requires one event per room, so `room_id` is unique.
    Lifting that constraint later is a non-breaking change.
    """

    id: int | None = Field(default=None, primary_key=True)
    room_id: int = Field(
        sa_column=Column(
            "room_id",
            Integer,
            ForeignKey("room.id", ondelete="CASCADE"),
            unique=True,
            index=True,
            nullable=False,
        ),
    )
    starts_at: datetime = Field(index=True)
    ends_at: datetime = Field(index=True)
    created_by: str = Field(index=True)  # identity_address of room creator
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoomEventRsvp(SQLModel, table=True):
    """A member's attendance declaration for a RoomEvent.

    A given user can hold at most one RSVP per event (enforced by the
    composite unique constraint), updated through upsert semantics.
    """

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(
        sa_column=Column(
            "event_id",
            Integer,
            ForeignKey("roomevent.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    user_id: int = Field(
        sa_column=Column(
            "user_id",
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    status: RsvpStatus
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    __table_args__ = (UniqueConstraint("event_id", "user_id"),)


class Game(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    sort_order: int = Field(index=True)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    identity_address: str = Field(index=True, unique=True)
    username: str = Field(
        default_factory=lambda: f"user_{secrets.token_hex(4)}",
        index=True,
        unique=True,
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login: datetime | None = Field(default=None)

    nonces: list[Nonce] = Relationship(back_populates="user")
    rooms: list[Room] = Relationship(back_populates="members", link_model=RoomMember)


class Nonce(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    identity_address: str = Field(index=True)
    value: str = Field(unique=True)

    expires_at: datetime
    used: bool = Field(default=False)

    user_id: int | None = Field(default=None, foreign_key="user.id")
    user: User | None = Relationship(back_populates="nonces")
