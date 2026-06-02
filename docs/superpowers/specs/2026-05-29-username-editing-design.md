# Issue #56 — Username editing with profanity stoplist

## Goal
Let an authenticated user set a custom, unique username (replacing the
auto-generated `user_<hex>`), validated against a public profanity stoplist
before saving. Usernames are public (chat, room rosters, RSVP lists), so basic
moderation is required.

## Existing state (no change needed)
- `User.username` is already `unique`, `index`, defaulting to `user_<hex>`
  (`backend/models.py`). It is part of the initial Alembic migration, so no DB
  migration is required.
- `GET /users/me` returns `{ id, identity_address, username, created_at,
  last_login, is_admin }`.
- Username already surfaces live in chat, rosters, and RSVPs (looked up by
  address), so an edit propagates automatically — no backfill needed.
- Auth: SvelteKit stores the JWT in a `session` cookie; server `load`/actions
  call the backend with `Authorization: Bearer ${session}`.

## Backend

### Stoplist (vendored)
- File: `backend/data/profanity_en.txt` — the LDNOOBW English list, one entry
  per line.
- Source: https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words
  file `en`, git blob `a438b9ca33af77341768bd6c63ce3e48e726b76e`, retrieved
  2026-05-29. Documented in the loader module.

### `backend/usernames.py`
- `USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")`
- `load_stoplist() -> frozenset[str]` — read the file once at import, lowercased,
  blanks stripped.
- `contains_profanity(name) -> bool` — lowercase `name`; reject if the whole
  string is in the set, or if any token (split on `_`/`-`) is in the set.
  Exact-word/token match avoids false positives like `assassin`/`classic`
  while catching `xX_fuck_Xx`. Multi-word stoplist phrases (with spaces) can
  never match a username and are simply inert.
- `UsernameError(StrEnum)` (or sentinel return) with members `invalid_format`,
  `profane` so the endpoint maps to status codes.
- `validate_username(name) -> UsernameError | None`.

### `PATCH /users/me`
- Body `UpdateUserRequest(BaseModel)`: `username: str`.
- Auth via existing `get_current_user_address`.
- Logic:
  1. `validate_username` → `invalid_format` ⇒ **400** "Username must be 3–20
     characters: letters, numbers, _ or -."
  2. `profane` ⇒ **400** "Username contains inappropriate language."
  3. If equal to the caller's current username ⇒ no-op success.
  4. Uniqueness: another user holds it ⇒ **409** "Username already taken."
  5. Assign, commit. `IntegrityError` on the unique constraint ⇒ **409**
     (race backstop).
- Returns the same dict shape as `GET /users/me`.

## Frontend

### Route `/profile`
- `+page.server.ts`:
  - `load`: redirect to `/auth` if no `session`; else `GET /users/me` with
    Bearer; return `{ identity_address, username, created_at, last_login }`.
  - action `update`: read `username` from form; `PATCH /users/me` with Bearer;
    `!ok` ⇒ `fail(status, { error: detail })`; ok ⇒ `{ success: true, username }`.
- `+page.svelte`: D2-retro UI reusing existing chrome components
  (`InnerPanel`, `SectionTitle`, `OrnateButton`, …). Read-only identity address,
  created_at, last_login + inline username edit form with a client-side regex
  hint and server-side error display, via `use:enhance`.

### Nav
- Add a `Profile` tab in `+layout.svelte`, shown only when authenticated. Add a
  minimal `+layout.server.ts` returning `{ isAuthenticated: !!cookies.get('session') }`.

## Testing
- Backend (TDD): `tests/test_users.py` — success; invalid regex (too short / bad
  chars); profanity rejected (case-insensitive + token form); 409 conflict;
  idempotent same-username; 401 unauthenticated; stoplist loads non-empty.
- Frontend: no test harness exists in the repo; verify the `/profile` flow
  manually on Docker.

## Out of scope
- The Python-2-style `except jwt.InvalidTokenError, KeyError:` at
  `main.py:227` (parses on 3.14 but binds to `KeyError` instead of catching it).
  Latent, currently harmless.
