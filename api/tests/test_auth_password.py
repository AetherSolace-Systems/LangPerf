from app.auth.password import hash_password, verify_password


def test_hash_and_verify_round_trip():
    hashed = hash_password("correcthorsebatterystaple")
    assert hashed != "correcthorsebatterystaple"
    assert verify_password("correcthorsebatterystaple", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hashes_are_different_for_same_password():
    a = hash_password("x")
    b = hash_password("x")
    assert a != b
