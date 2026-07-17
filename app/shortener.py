import random
import string

_ALPHABET = string.ascii_letters + string.digits  # 62 characters
_CODE_LENGTH = 6
_MAX_RETRIES = 10


def generate_code() -> str:
    """Return a random 6-character base-62 string (e.g. 'aB3xZ9').

    The caller is responsible for checking uniqueness and retrying if needed.
    With 62^6 ≈ 56 billion possible codes, collisions are extremely rare
    but the DB insertion in crud.py handles them gracefully.
    """
    return "".join(random.choices(_ALPHABET, k=_CODE_LENGTH))
