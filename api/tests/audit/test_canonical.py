"""JCS (RFC 8785) canonical encoding tests.

Golden-file tests gate every change to the canonicalizer; an accidental
divergence would invalidate every historical signature.
"""
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
