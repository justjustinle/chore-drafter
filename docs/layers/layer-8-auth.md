# Layer 8: Auth with API keys

## What it does
Every member gets a secret API key. Requests send it in the `X-API-Key`
header, and the server works out who is calling from the key alone. Members
can now only act as themselves, and owner-only actions are enforced for real.

## Files
- `app/identity.py` is the only file whose job changed. `get_caller` now looks
  the key up instead of reading an email header, and returns the `Member`.
  `require_member` and `require_owner` keep the same shape, which is why
  every endpoint written since Layer 3 only needed its type hint updated.
- `app/models.py` and migration `0004_member_api_key.py`: `member.api_key_hash`.
  The migration names its unique constraint by hand, because Alembic
  generated it with the name `None`, which the downgrade could not drop.
- `app/routers/households.py` and `invites.py`: return the key once, on creation.
- `tests/helpers.py`: `KEYS` remembers each test person's key, so
  `as_user(email)` sends the right header.
- `tests/test_auth.py`: the Layer 8 checks.

## Things worth noticing
- **Hash, don't store.** If the database leaked, the hashes are useless:
  you cannot turn a SHA-256 hash back into the key. A fast hash is fine here
  because the keys are long random strings; passwords, which people choose,
  need a deliberately slow hash such as bcrypt or argon2.
- **401 vs 403.** 401 means "I don't know who you are" (no key, or a wrong
  one). 403 means "I know who you are, and you are not allowed".
- **Why the change was small.** Layer 3 put every identity check in one file.
  Swapping how identity works touched that file, not 30 endpoints.

## Interview questions
1. Why store a hash of the API key rather than the key itself? Why is SHA-256 acceptable here when it would not be for passwords?
2. What is the difference between a 401 and a 403? Give an example of each from this app.
3. How did keeping identity checks in one module make this layer smaller?
