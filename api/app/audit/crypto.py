"""Signing primitives for the audit chain.

Ed25519 is primary (FIPS 186-5 approved). ECDSA P-384 is pluggable for
legacy FIPS environments. Vetted libraries only: ``pynacl`` for Ed25519,
``cryptography`` for P-384 and PEM serialization. Never roll our own.
"""
from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey as NaclSigningKey
from nacl.signing import VerifyKey as NaclVerifyKey

SIG_ED25519 = "ed25519"
SIG_ECDSA_P384 = "ecdsa-p384"

_P384_CURVE = ec.SECP384R1()


class VerifyError(Exception):
    """Signature verification failed."""


class _P384PublicKey:
    """Thin wrapper so bytes() round-trips correctly, matching the NaCl VerifyKey contract."""

    def __init__(self, key):
        self._key = key

    def __bytes__(self) -> bytes:
        return self._key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    # Expose the underlying key for verify()
    @property
    def raw(self):
        return self._key


def generate_keypair(alg: str) -> tuple[bytes, bytes]:
    """Return ``(private_bytes, public_bytes)`` for ``alg``."""
    if alg == SIG_ED25519:
        priv = NaclSigningKey.generate()
        return bytes(priv), bytes(priv.verify_key)
    if alg == SIG_ECDSA_P384:
        priv = ec.generate_private_key(_P384_CURVE)
        priv_bytes = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return priv_bytes, pub_bytes
    raise ValueError(f"unknown algorithm: {alg!r}")


def load_public_key(public_bytes: bytes, alg: str):
    """Rehydrate a public key object from its serialized bytes."""
    if alg == SIG_ED25519:
        return NaclVerifyKey(public_bytes)
    if alg == SIG_ECDSA_P384:
        return _P384PublicKey(serialization.load_pem_public_key(public_bytes))
    raise ValueError(f"unknown algorithm: {alg!r}")


def sign(private_bytes: bytes, data: bytes, alg: str) -> bytes:
    """Return a signature over ``data`` using the private key."""
    if alg == SIG_ED25519:
        return bytes(NaclSigningKey(private_bytes).sign(data).signature)
    if alg == SIG_ECDSA_P384:
        priv = serialization.load_pem_private_key(private_bytes, password=None)
        return priv.sign(data, ec.ECDSA(hashes.SHA384()))
    raise ValueError(f"unknown algorithm: {alg!r}")


def verify(public_bytes: bytes | _P384PublicKey, signature: bytes, data: bytes, alg: str) -> None:
    """Raise ``VerifyError`` if ``signature`` does not verify ``data``.

    Malformed key bytes (wrong length for Ed25519; non-PEM for P-384) also
    surface as ``VerifyError`` rather than leaking ``ValueError`` from the
    underlying library.
    """
    if alg == SIG_ED25519:
        try:
            NaclVerifyKey(public_bytes).verify(data, signature)
        except (ValueError, BadSignatureError) as exc:
            raise VerifyError(f"ed25519 verification failed: {exc}") from exc
        return
    if alg == SIG_ECDSA_P384:
        try:
            # Accept either raw PEM bytes or the _P384PublicKey wrapper.
            if isinstance(public_bytes, _P384PublicKey):
                pub = public_bytes.raw
            else:
                pub = serialization.load_pem_public_key(public_bytes)
            pub.verify(signature, data, ec.ECDSA(hashes.SHA384()))
        except (ValueError, InvalidSignature) as exc:
            raise VerifyError(f"ecdsa-p384 verification failed: {exc}") from exc
        return
    raise ValueError(f"unknown algorithm: {alg!r}")
