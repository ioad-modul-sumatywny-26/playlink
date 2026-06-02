"""Username validation: format rules and a public profanity stoplist.

The stoplist is the LDNOOBW English word list, vendored at
``data/profanity_en.txt`` so the check is offline and version-pinned.

Source: https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words
File ``en``, git blob ``a438b9ca33af77341768bd6c63ce3e48e726b76e``,
retrieved 2026-05-29.
"""

import re
from functools import lru_cache
from pathlib import Path

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")

_STOPLIST_PATH = Path(__file__).parent / "data" / "profanity_en.txt"
_TOKEN_SPLIT = re.compile(r"[_-]")


@lru_cache(maxsize=1)
def load_stoplist() -> frozenset[str]:
    """Load the profanity stoplist once, lowercased, blanks dropped."""
    lines = _STOPLIST_PATH.read_text(encoding="utf-8").splitlines()
    return frozenset(word.strip().lower() for word in lines if word.strip())


def contains_profanity(name: str) -> bool:
    """True if ``name`` as a whole, or any ``_``/``-`` token, is a stoplist word.

    Exact whole-string and per-token matching (rather than substring) avoids
    false positives like ``assassin`` or ``classic`` while still catching
    evasions such as ``xX_fuck_Xx``.
    """
    stoplist = load_stoplist()
    lowered = name.lower()
    if lowered in stoplist:
        return True
    return any(token in stoplist for token in _TOKEN_SPLIT.split(lowered) if token)


def validate_username(name: str) -> str | None:
    """Return an error code, or ``None`` when valid.

    Codes: ``"invalid_format"`` (fails the regex), ``"profane"`` (hits the
    stoplist).
    """
    if not USERNAME_RE.match(name):
        return "invalid_format"
    if contains_profanity(name):
        return "profane"
    return None
