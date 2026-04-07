import secrets
from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


class Room(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    game: str
    players_max: int
    players_active: int = Field(default=0)
    created_by: str = Field(index=True)  # identity_address of creator
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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


class Nonce(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    identity_address: str = Field(index=True)
    value: str = Field(unique=True)

    expires_at: datetime
    used: bool = Field(default=False)

    user_id: int | None = Field(default=None, foreign_key="user.id")
    user: User | None = Relationship(back_populates="nonces")
