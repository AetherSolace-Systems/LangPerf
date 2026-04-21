"""RFC 6962 Certificate Transparency Merkle tree primitives.

Implements the tree construction, inclusion proofs, and consistency proofs
defined in RFC 6962 §2.1. Key properties:

- `merkle_root` builds the canonical left-heavy binary tree using the
  largest-power-of-two split, so trees are deterministic for a given leaf list.
- `verify_inclusion_proof` recomputes the root from the leaf and path; it
  never trusts the proof inputs — a forged or tampered proof will produce a
  different root and return False.
- `verify_consistency_proof` follows the RFC 6962 §2.1.2 pseudocode exactly.
  The strip-trailing-bits loop and the seeded fn/sn walk are load-bearing;
  simpler-looking alternatives subtly mishandle power-of-two boundaries.
"""
from __future__ import annotations

from app.audit.hashing import compute_internal_hash


def _largest_power_of_two_less_than(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        raise ValueError("merkle_root requires at least one leaf")
    if len(leaves) == 1:
        return leaves[0]
    k = _largest_power_of_two_less_than(len(leaves))
    left = merkle_root(leaves[:k])
    right = merkle_root(leaves[k:])
    return compute_internal_hash(left, right)


# ---------------------------------------------------------------------------
# Inclusion proof
# ---------------------------------------------------------------------------


def inclusion_proof(leaves: list[bytes], index: int) -> list[bytes]:
    if not 0 <= index < len(leaves):
        raise ValueError("index out of range")
    return _inclusion_proof_recursive(leaves, index)


def _inclusion_proof_recursive(leaves: list[bytes], index: int) -> list[bytes]:
    n = len(leaves)
    if n == 1:
        return []
    k = _largest_power_of_two_less_than(n)
    if index < k:
        return _inclusion_proof_recursive(leaves[:k], index) + [merkle_root(leaves[k:])]
    return _inclusion_proof_recursive(leaves[k:], index - k) + [merkle_root(leaves[:k])]


def verify_inclusion_proof(
    *,
    leaf_hash: bytes,
    index: int,
    tree_size: int,
    proof: list[bytes],
    root: bytes,
) -> bool:
    if not 0 <= index < tree_size:
        return False
    fn = leaf_hash
    sn = tree_size - 1
    r = index
    for p in proof:
        if sn == 0:
            return False
        if r & 1 or r == sn:
            fn = compute_internal_hash(p, fn)
            while not (r & 1) and r != 0:
                r >>= 1
                sn >>= 1
        else:
            fn = compute_internal_hash(fn, p)
        r >>= 1
        sn >>= 1
    return sn == 0 and fn == root


# ---------------------------------------------------------------------------
# Consistency proof
# ---------------------------------------------------------------------------


def consistency_proof(leaves: list[bytes], old_size: int) -> list[bytes]:
    if not 0 < old_size <= len(leaves):
        raise ValueError("invalid old_size")
    if old_size == len(leaves):
        return []
    return _consistency_proof_recursive(leaves, old_size, True)


def _consistency_proof_recursive(leaves: list[bytes], m: int, b: bool) -> list[bytes]:
    n = len(leaves)
    if m == n:
        return [] if b else [merkle_root(leaves)]
    k = _largest_power_of_two_less_than(n)
    if m <= k:
        return _consistency_proof_recursive(leaves[:k], m, b) + [merkle_root(leaves[k:])]
    return _consistency_proof_recursive(leaves[k:], m - k, False) + [merkle_root(leaves[:k])]


def verify_consistency_proof(
    *,
    old_size: int,
    new_size: int,
    old_root: bytes,
    new_root: bytes,
    proof: list[bytes],
) -> bool:
    """RFC 6962 §2.1.2 consistency proof verification.

    The strip-trailing-bits loop normalises both node indices so that the
    walk below handles the case where old_size is already a complete subtree
    without special-casing it. The seeded fn/sn split then simultaneously
    reconstructs both the old and new roots; agreement with the supplied
    roots is the proof of consistency.
    """
    if old_size < 0 or old_size > new_size:
        return False
    if old_size == 0:
        return len(proof) == 0
    if old_size == new_size:
        return len(proof) == 0 and old_root == new_root

    node = old_size - 1
    last_node = new_size - 1

    # Strip common trailing bits — move both pointers up to where the paths
    # first diverge. After this loop node is the "interesting" ancestor.
    while node & 1:
        node >>= 1
        last_node >>= 1

    proof = list(proof)

    if node:
        if not proof:
            return False
        seed = proof[0]
        proof = proof[1:]
    else:
        seed = old_root

    fn = sn = seed

    while node or last_node:
        if node & 1 or node == last_node:
            if not proof:
                return False
            fn = compute_internal_hash(proof[0], fn)
            sn = compute_internal_hash(proof[0], sn)
            proof = proof[1:]
            while node and not (node & 1):
                node >>= 1
                last_node >>= 1
        else:
            if not proof:
                return False
            sn = compute_internal_hash(sn, proof[0])
            proof = proof[1:]
        node >>= 1
        last_node >>= 1

    if proof:
        return False
    return fn == old_root and sn == new_root
