"""JCS (RFC 8785) canonical encoding tests.

Golden-file tests gate every change to the canonicalizer; an accidental
divergence would invalidate every historical signature.
"""
import pytest

from app.audit.canonical import canonical_encode, canonical_hash


def test_dict_keys_sorted_lexicographically():
    assert canonical_encode({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_nested_dict_keys_sorted():
    assert canonical_encode({"z": {"b": 1, "a": 2}, "a": 3}) == b'{"a":3,"z":{"a":2,"b":1}}'


def test_timestamp_represented_as_iso_string():
    # Timestamps must be strings, not floats — JCS number constraints are too
    # narrow for nanosecond precision and not all OTLP sources emit epoch ms.
    payload = {"ts": "2026-04-21T18:00:00.123456Z", "v": 1}
    assert canonical_encode(payload) == b'{"ts":"2026-04-21T18:00:00.123456Z","v":1}'


def test_unicode_normalized_to_nfc():
    # "é" can be composed (U+00E9) or decomposed (U+0065 U+0301). JCS mandates NFC.
    composed = {"x": "\u00e9"}
    decomposed = {"x": "e\u0301"}
    assert canonical_encode(composed) == canonical_encode(decomposed)


def test_canonical_hash_is_sha256_of_encoding():
    import hashlib
    payload = {"hello": "world"}
    expected = hashlib.sha256(b'{"hello":"world"}').digest()
    assert canonical_hash(payload) == expected


def test_empty_dict_is_valid():
    assert canonical_encode({}) == b"{}"


def test_arrays_preserve_order():
    assert canonical_encode({"xs": [3, 1, 2]}) == b'{"xs":[3,1,2]}'


def test_rejects_keys_that_collide_under_nfc():
    # "e\u0301" (decomposed) and "\u00e9" (composed) are both "é" after NFC.
    d = {"e\u0301": 1, "\u00e9": 2}
    with pytest.raises(ValueError, match="collide"):
        canonical_encode(d)


def test_rejects_nan():
    with pytest.raises(ValueError, match="not canonicalizable"):
        canonical_encode({"x": float("nan")})


def test_rejects_infinity():
    with pytest.raises(ValueError, match="not canonicalizable"):
        canonical_encode({"x": float("inf")})


def test_float_and_int_canonicalize_identically_when_equal():
    # rfc8785 strips trailing .0 per JCS number rules. Pin this behavior so a
    # future library version can't silently change it.
    assert canonical_encode({"a": 1.0}) == canonical_encode({"a": 1}) == b'{"a":1}'
