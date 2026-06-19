"""Shared slowapi rate limiter.

Defined in its own module so every router can apply ``@limiter.limit(...)``
against the same instance that ``main`` registers on ``app.state.limiter``.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
