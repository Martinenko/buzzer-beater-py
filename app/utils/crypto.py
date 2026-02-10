from cryptography.fernet import Fernet
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.config import get_settings


def _get_fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode())


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value)
