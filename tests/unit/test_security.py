from app.core.security import hash_password, verify_password


def test_hash_password_produces_verifiable_hash() -> None:
    password = "correct-horse-battery-staple"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password("wrong-password", hashed) is False
