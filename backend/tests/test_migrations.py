from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_head_on_empty_sqlite_database(tmp_path, monkeypatch):
    db_path = tmp_path / "migration-smoke.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert {
        "game",
        "message",
        "nonce",
        "room",
        "roomevent",
        "roomeventrsvp",
        "roommember",
        "user",
    }.issubset(tables)

    room_columns = {column["name"] for column in inspector.get_columns("room")}
    assert {"description", "communicator_link", "requirements"}.issubset(room_columns)

    event_columns = {column["name"] for column in inspector.get_columns("roomevent")}
    assert {"starts_at", "ends_at", "created_by", "updated_at"}.issubset(event_columns)
