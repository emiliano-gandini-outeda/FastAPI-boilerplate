"""Unit tests for user schema validation."""

import pytest
from pydantic import ValidationError

from src.modules.user.schemas import UserCreate


def _make_user_create(password: str) -> UserCreate:
    return UserCreate(
        name="Test User",
        username="testuser",
        email="test@example.com",
        password=password,
    )


def test_password_meeting_policy_is_accepted():
    """A password with 8+ chars, number, upper, lower and special passes."""
    user = _make_user_create("Str1ngst!")
    assert user.password == "Str1ngst!"


@pytest.mark.parametrize(
    ("password", "missing"),
    [
        ("aaaaaaaa", ["a number", "an uppercase letter", "a special character"]),
        ("AAAAAAAA", ["a number", "a lowercase letter", "a special character"]),
        ("12345678", ["an uppercase letter", "a lowercase letter", "a special character"]),
        ("Aa1!bcd", ["at least 8 characters"]),
        ("Aa1bcdef", ["a special character"]),
    ],
)
def test_password_policy_rejects_weak_passwords(password: str, missing: list[str]):
    """Weak passwords are rejected and the error lists every missing requirement."""
    with pytest.raises(ValidationError) as exc_info:
        _make_user_create(password)

    message = str(exc_info.value)
    for requirement in missing:
        assert requirement in message
