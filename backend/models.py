import secrets
from datetime import UTC, datetime, timedelta

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
    created_by: str = Field(index=True)  # identity_address of creator
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=1))

    members: list["User"] = Relationship(back_populates="rooms", link_model=RoomMember)


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

    nonces: list["Nonce"] = Relationship(back_populates="user")
    rooms: list["Room"] = Relationship(back_populates="members", link_model=RoomMember)


class Nonce(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    identity_address: str = Field(index=True)
    value: str = Field(unique=True)

    expires_at: datetime
    used: bool = Field(default=False)

    user_id: int | None = Field(default=None, foreign_key="user.id")
    user: User | None = Relationship(back_populates="nonces")
