from app.services.passwords import hash_password, verify_password


def test_passwords_are_hashed_with_argon2_and_can_be_verified() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert password_hash.startswith("$argon2")
    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("incorrect password", password_hash) is False
