"""Pydantic request schemas for the HTTP API."""

from datetime import datetime

from pydantic import BaseModel, HttpUrl
from pydantic import Field as PydField

from models import RsvpStatus


class VerifyRequest(BaseModel):
    address: str
    nonce: str
    signature: str


class CreateRoomRequest(BaseModel):
    name: str
    game: str = PydField(min_length=1, max_length=100)
    lobby_location: str = PydField(min_length=1, max_length=50)
    players_max: int
    description: str | None = PydField(default=None, max_length=500)
    communicator_link: HttpUrl | None = None
    requirements: str | None = PydField(default=None, max_length=1000)


class ScheduleEventRequest(BaseModel):
    """Body for `PUT /rooms/{name}/event`. Both timestamps must be in the future."""

    starts_at: datetime
    ends_at: datetime


class SetRsvpRequest(BaseModel):
    """Body for `PUT /rooms/{name}/event/rsvp`."""

    status: RsvpStatus


class CreateGameRequest(BaseModel):
    """Body for `POST /games` — admin adds a new game category."""

    name: str = PydField(min_length=1, max_length=100)


class UpdateUserRequest(BaseModel):
    username: str
