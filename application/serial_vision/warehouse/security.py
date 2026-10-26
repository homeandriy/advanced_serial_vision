from __future__ import annotations

import hashlib
import re
import secrets
import string
from dataclasses import dataclass
from enum import StrEnum

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError


class WarehouseError(Exception):
    def __init__(self, code: str, status: int = 422) -> None:
        self.code, self.status = code, status
        super().__init__(code)


class Role(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    STOREKEEPER = "storekeeper"


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    role: Role
    must_change: bool
    token_hash: str
    kind: str
    scope: str


PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
SPECIAL = frozenset(string.punctuation)


def validate_password(password: object) -> str:
    if (
        not isinstance(password, str)
        or not 8 <= len(password) <= 256
        or not (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
            and any(char in SPECIAL for char in password)
        )
    ):
        raise WarehouseError("wh_password_policy")
    return password


def password_matches(encoded: str, password: object) -> bool:
    if not isinstance(password, str) or len(password) > 256:
        return False
    try:
        return PASSWORDS.verify(encoded, password)
    except VerificationError:
        return False


def email_address(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip())
    ):
        raise WarehouseError("wh_email_invalid")
    return value.strip().casefold()


def text(data: dict[str, object], key: str, maximum: int = 500, required: bool = True) -> str:
    value = data.get(key, "")
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (required and not value.strip())
        or "\0" in value
    ):
        raise WarehouseError("wh_input_invalid")
    return value.strip()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def temporary_password() -> str:
    return "Aa1_" + secrets.token_urlsafe(18)
