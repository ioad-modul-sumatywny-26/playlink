import os
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

# Load .env from project root (../.env) if it exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# Automatic local development redirection:
# If host is 'db' and we are NOT in a docker container, swap to 'localhost'
if "@db:" in DATABASE_URL and not Path("/.dockerenv").exists():
    DATABASE_URL = DATABASE_URL.replace("@db:", "@localhost:")

engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
