from cryptography.fernet import Fernet

from app.config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().bot_token_encryption_key.encode())


def encrypt_bot_token(token: str) -> bytes:
    return _fernet().encrypt(token.encode())


def decrypt_bot_token(encrypted: bytes) -> str:
    return _fernet().decrypt(encrypted).decode()
