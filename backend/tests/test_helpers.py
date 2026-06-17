from datetime import UTC, datetime

import main
from models import Message, Room, User


def test_parse_admin_addresses_trims_lowercases_and_skips_empty_values():
    raw = " 0xABC , ,0xdef,  0x123  "

    assert main._parse_admin_addresses(raw) == {"0xabc", "0xdef", "0x123"}


def test_parse_admin_addresses_returns_empty_set_for_missing_value():
    assert main._parse_admin_addresses(None) == set()
    assert main._parse_admin_addresses("") == set()


def test_is_admin_address_is_case_insensitive():
    original = set(main.ADMIN_ADDRESSES)
    main.ADMIN_ADDRESSES.clear()
    main.ADMIN_ADDRESSES.add("0xabc")
    try:
        assert main.is_admin_address("0xABC") is True
        assert main.is_admin_address("0xdef") is False
    finally:
        main.ADMIN_ADDRESSES.clear()
        main.ADMIN_ADDRESSES.update(original)


def test_hash_nonce_is_stable_and_not_plaintext():
    nonce = "challenge-value"

    hashed = main.hash_nonce(nonce)

    assert hashed == main.hash_nonce(nonce)
    assert hashed != nonce
    assert len(hashed) == 64


def test_iso_appends_z_for_naive_datetime_and_preserves_aware_offset():
    naive = datetime(2026, 1, 2, 3, 4, 5)
    aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    assert main._iso(naive) == "2026-01-02T03:04:05Z"
    assert main._iso(aware) == "2026-01-02T03:04:05+00:00"


def test_members_payload_is_compact_roster_shape():
    room = Room(name="lobby", game="Quake III Arena", players_max=2, created_by="0x1")
    room.members.extend(
        [
            User(identity_address="0x1", username="alice"),
            User(identity_address="0x2", username="bob"),
        ]
    )

    assert main._members_payload(room) == [
        {"address": "0x1", "username": "alice", "is_admin": False},
        {"address": "0x2", "username": "bob", "is_admin": False},
    ]


def test_msg_dict_keeps_public_chat_payload_shape():
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    msg = Message(
        id=42,
        room_id=7,
        sender_address="0xSender",
        content="hello",
        created_at=created_at,
    )

    assert main._msg_dict(msg, "alice") == {
        "id": 42,
        "sender_address": "0xSender",
        "sender_username": "alice",
        "content": "hello",
        "created_at": "2026-01-02T03:04:05+00:00",
    }
