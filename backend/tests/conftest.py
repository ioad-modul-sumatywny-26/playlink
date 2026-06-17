import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from main import app, get_session
from models import Game


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    Game(name="Quake III Arena", sort_order=1),
                    Game(name="Diablo II", sort_order=2),
                    Game(name="StarCraft", sort_order=3),
                    Game(name="Half-Life", sort_order=4),
                    Game(name="Unreal Tournament", sort_order=5),
                ]
            )
            session.commit()
            yield session
    finally:
        engine.dispose()


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def disable_rate_limit():
    app.state.limiter.enabled = False
