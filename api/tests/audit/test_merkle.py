"""RFC 6962 Merkle tree tests — root, inclusion proof, consistency proof."""
import pytest

from app.audit.merkle import (
    merkle_root,
    inclusion_proof,
    verify_inclusion_proof,
    consistency_proof,
    verify_consistency_proof,
)
from app.audit.hashing import compute_leaf_hash, compute_internal_hash


def _leaves(n: int) -> list[bytes]:
    return [compute_leaf_hash(bytes([i]) * 32) for i in range(n)]


def test_single_leaf_root_is_the_leaf():
    leaves = _leaves(1)
    assert merkle_root(leaves) == leaves[0]


def test_two_leaf_root_is_hash_of_concat():
    leaves = _leaves(2)
    expected = compute_internal_hash(leaves[0], leaves[1])
    assert merkle_root(leaves) == expected


def test_three_leaf_tree_matches_rfc6962_left_heavy_split():
    leaves = _leaves(3)
    left = compute_internal_hash(leaves[0], leaves[1])
    right = leaves[2]
    assert merkle_root(leaves) == compute_internal_hash(left, right)


@pytest.mark.parametrize("n", [1, 2, 3, 7, 8, 15, 16, 100])
def test_inclusion_proof_roundtrip_for_every_leaf(n):
    leaves = _leaves(n)
    root = merkle_root(leaves)
    for idx in range(n):
        proof = inclusion_proof(leaves, idx)
        assert verify_inclusion_proof(
            leaf_hash=leaves[idx], index=idx, tree_size=n, proof=proof, root=root
        ) is True


def test_inclusion_proof_detects_tamper():
    leaves = _leaves(8)
    root = merkle_root(leaves)
    proof = inclusion_proof(leaves, 3)
    tampered = bytes([b ^ 0xFF for b in leaves[3]])
    assert verify_inclusion_proof(
        leaf_hash=tampered, index=3, tree_size=8, proof=proof, root=root
    ) is False


@pytest.mark.parametrize("n1,n2", [(1, 2), (1, 8), (5, 8), (7, 8), (8, 16)])
def test_consistency_proof_roundtrip(n1, n2):
    leaves = _leaves(n2)
    root1 = merkle_root(leaves[:n1])
    root2 = merkle_root(leaves)
    proof = consistency_proof(leaves, n1)
    assert verify_consistency_proof(
        old_size=n1, new_size=n2, old_root=root1, new_root=root2, proof=proof
    ) is True


def test_consistency_proof_detects_different_prefix():
    leaves_a = _leaves(8)
    leaves_b = [compute_leaf_hash(bytes([i + 1]) * 32) for i in range(8)]
    root_a1 = merkle_root(leaves_a[:4])
    root_b2 = merkle_root(leaves_b)
    proof = consistency_proof(leaves_b, 4)
    assert verify_consistency_proof(
        old_size=4, new_size=8, old_root=root_a1, new_root=root_b2, proof=proof
    ) is False
