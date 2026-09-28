"""Encrypting stored third-party credentials (RS.ge service users) with CREDENTIALS_KEY (a Fernet key).

Without a key, nothing can be stored: callers treat that as "not set up".
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CredentialsUnavailable(RuntimeError):
    """No key configured, or the stored value can't be decrypted with the current key."""


def cipher() -> Fernet | None:
    key = settings.credentials_key.strip()
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except ValueError as e:
        raise CredentialsUnavailable("CREDENTIALS_KEY is not a valid Fernet key") from e


def encrypt(value: str) -> str:
    f = cipher()
    if f is None:
        raise CredentialsUnavailable("CREDENTIALS_KEY is not set")
    return f.encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    f = cipher()
    if f is None:
        raise CredentialsUnavailable("CREDENTIALS_KEY is not set")
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise CredentialsUnavailable("stored credentials can't be decrypted with this key") from e
