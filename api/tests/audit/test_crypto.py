"""Signing primitive tests — Ed25519 + ECDSA P-384 round-trips."""
import pytest
from app.audit.crypto import (
    SIG_ECDSA_P384,
    SIG_ED25519,
    VerifyError,
    generate_keypair,
    load_public_key,
    sign,
    verify,
)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_generate_sign_verify_roundtrip(alg):
    priv, pub = generate_keypair(alg)
    data = b"the quick brown fox"
    sig = sign(priv, data, alg)
    # verify() returns None on success, raises on failure
    verify(pub, sig, data, alg)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_verify_rejects_tampered_data(alg):
    priv, pub = generate_keypair(alg)
    sig = sign(priv, b"original", alg)
    with pytest.raises(VerifyError):
        verify(pub, sig, b"tampered", alg)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_verify_rejects_wrong_key(alg):
    _, pub_a = generate_keypair(alg)
    priv_b, _ = generate_keypair(alg)
    sig_b = sign(priv_b, b"data", alg)
    with pytest.raises(VerifyError):
        verify(pub_a, sig_b, b"data", alg)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_public_key_roundtrip_through_serialization(alg):
    _, pub = generate_keypair(alg)
    serialized = bytes(pub)
    restored = load_public_key(serialized, alg)
    assert bytes(restored) == serialized


def test_unknown_algorithm_raises():
    priv, _ = generate_keypair(SIG_ED25519)
    with pytest.raises(ValueError, match="unknown algorithm"):
        sign(priv, b"x", "not-an-alg")


def test_verify_raises_verify_error_for_malformed_ed25519_key():
    priv, _ = generate_keypair(SIG_ED25519)
    sig = sign(priv, b"x", SIG_ED25519)
    with pytest.raises(VerifyError):
        verify(b"not-a-key", sig, b"x", SIG_ED25519)


def test_verify_raises_verify_error_for_malformed_p384_key():
    priv, _ = generate_keypair(SIG_ECDSA_P384)
    sig = sign(priv, b"x", SIG_ECDSA_P384)
    with pytest.raises(VerifyError):
        verify(b"not-pem-bytes", sig, b"x", SIG_ECDSA_P384)
