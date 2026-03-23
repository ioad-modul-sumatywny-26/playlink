import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import jwt
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.address import to_checksum_address
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import Nonce, User

# Load .env from project root if it exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is not set")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
NONCE_EXPIRATION_MINUTES = int(os.getenv("NONCE_EXPIRATION_MINUTES", "5"))
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))


# --- Schemas ---
class VerifyRequest(BaseModel):
    address: str
    nonce: str
    signature: str


# --- Helpers ---
def hash_nonce(nonce_value: str) -> str:
    return hashlib.sha256(nonce_value.encode()).hexdigest()


SessionDep = Annotated[Session, Depends(get_session)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify", auto_error=False)


async def get_current_user_address(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.InvalidTokenError, KeyError:
        raise HTTPException(status_code=401, detail="Invalid token") from None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

# Configure CORS
origins = [
    "https://playlink.bartek.monster",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---


@app.get("/")
def read_root():
    return {"status": "ok", "service": "playlink-auth"}


@app.post("/auth/request-nonce")
def request_nonce(address: str, session: SessionDep):
    """
    Request a one-time nonce for an identity address.
    """
    try:
        checksum_address = to_checksum_address(address)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid identity address format"
        ) from None

    # Upsert User
    user = session.exec(
        select(User).where(User.identity_address == checksum_address)
    ).first()
    if not user:
        user = User(identity_address=checksum_address)
        session.add(user)
        session.commit()
        session.refresh(user)

    # Generate & Hash Nonce
    nonce_value = str(uuid.uuid4())
    hashed_value = hash_nonce(nonce_value)

    # Invalidate previous unused nonces for this identity
    previous_nonces = session.exec(
        select(Nonce).where(
            Nonce.identity_address == checksum_address,
            Nonce.used == False,  # noqa: E712
        )
    ).all()
    for old_nonce in previous_nonces:
        old_nonce.used = True
        session.add(old_nonce)

    # Store new hashed nonce
    expires_at = datetime.now(UTC) + timedelta(minutes=NONCE_EXPIRATION_MINUTES)
    db_nonce = Nonce(
        identity_address=checksum_address,
        value=hashed_value,
        expires_at=expires_at,
        user_id=user.id,
    )
    session.add(db_nonce)
    session.commit()

    return {"nonce": nonce_value}


@app.post("/auth/verify")
def verify_signature(body: VerifyRequest, session: SessionDep):
    """
    Verify signature against a nonce and issue a JWT.
    """
    address = body.address
    nonce = body.nonce
    signature = body.signature

    try:
        checksum_address = to_checksum_address(address)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid identity address format"
        ) from None

    hashed_provided_nonce = hash_nonce(nonce)

    # Fetch matching unused & unexpired nonce
    db_nonce = session.exec(
        select(Nonce).where(
            Nonce.identity_address == checksum_address,
            Nonce.value == hashed_provided_nonce,
            Nonce.used == False,  # noqa: E712
            Nonce.expires_at > datetime.now(UTC),
        )
    ).first()

    if not db_nonce:
        raise HTTPException(status_code=401, detail="Invalid or expired challenge")

    # Recover address from signature
    message_text = f"Sign in to Playlink\nNonce: {nonce}"
    message = encode_defunct(text=message_text)

    try:
        recovered_address = Account.recover_message(message, signature=signature)
    except Exception:
        raise HTTPException(
            status_code=401, detail="Invalid signature format"
        ) from None

    if recovered_address.lower() != checksum_address.lower():
        raise HTTPException(status_code=401, detail="Identity verification failed")

    # Success: Mark nonce as used & update user
    db_nonce.used = True
    session.add(db_nonce)

    user = session.get(User, db_nonce.user_id)
    if user:
        user.last_login = datetime.now(UTC)
        session.add(user)

    session.commit()

    # Generate JWT
    token_data = {
        "sub": checksum_address,
        "username": user.username if user else "Unknown",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=JWT_EXPIRATION_MINUTES),
        "iss": "playlink-auth",
    }
    token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return {"token": token, "username": user.username if user else "Unknown"}


@app.get("/users/me", response_model=User)
def get_me(
    session: SessionDep,
    address: Annotated[str, Depends(get_current_user_address)],
):
    user = session.exec(select(User).where(User.identity_address == address)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
