import hashlib
from typing import Dict, List, Tuple


class SparseMerkleTree:
    """
    Fully corrected and verified 256-bit Sparse Merkle Tree (SMT).
    Guarantees mathematically sound proof generation and bottom-up verification.
    """
    DEFAULT_ZERO: List[bytes] = []

    def __init__(self, depth: int = 256):
        self.depth = depth
        self.leaves: Dict[bytes, bytes] = {}
        self._init_default_hashes()

    @classmethod
    def _init_default_hashes(cls):
        """Precomputes empty subtree root hashes for levels 0 to 256."""
        if cls.DEFAULT_ZERO:
            return
        
        # Base leaf default value
        current = hashlib.sha256(b"").digest()
        cls.DEFAULT_ZERO = [current]
        
        for _ in range(256):
            current = hashlib.sha256(current + current).digest()
            cls.DEFAULT_ZERO.append(current)

    @staticmethod
    def _hash_node(left: bytes, right: bytes) -> bytes:
        return hashlib.sha256(left + right).digest()

    @staticmethod
    def _to_bits(key_hash: bytes) -> str:
        return bin(int.from_bytes(key_hash, byteorder='big'))[2:].zfill(256)

    def update(self, key: bytes, value: bytes) -> bytes:
        """Inserts or updates a state key-value pair and returns the new Root Hash."""
        key_hash = hashlib.sha256(key).digest()
        val_hash = hashlib.sha256(value).digest()
        self.leaves[key_hash] = val_hash
        return self.get_root()

    def get_root(self) -> bytes:
        return self._compute_root(self.leaves, 0)

    def _compute_root(self, leaves: Dict[bytes, bytes], depth: int) -> bytes:
        if not leaves:
            return self.DEFAULT_ZERO[self.depth - depth]
        if depth == self.depth:
            return list(leaves.values())[0]

        left, right = {}, {}
        for k, v in leaves.items():
            if self._to_bits(k)[depth] == '0':
                left[k] = v
            else:
                right[k] = v

        return self._hash_node(
            self._compute_root(left, depth + 1),
            self._compute_root(right, depth + 1)
        )

    def create_proof(self, key: bytes) -> Tuple[bytes, List[bytes]]:
        """
        Generates an inclusion proof path for a given key.
        Proof array is ordered from leaf level (index 0) to root level (index 255).
        """
        key_hash = hashlib.sha256(key).digest()
        val_hash = self.leaves.get(key_hash, self.DEFAULT_ZERO[0])
        bits = self._to_bits(key_hash)
        
        proof_top_down: List[bytes] = []
        current_leaves = self.leaves

        for depth in range(self.depth):
            left, right = {}, {}
            for k, v in current_leaves.items():
                if self._to_bits(k)[depth] == '0':
                    left[k] = v
                else:
                    right[k] = v

            if bits[depth] == '0':
                proof_top_down.append(self._compute_root(right, depth + 1))
                current_leaves = left
            else:
                proof_top_down.append(self._compute_root(left, depth + 1))
                current_leaves = right

        # Reverse proof so index 0 = leaf sibling, index 255 = root sibling
        proof_bottom_up = list(reversed(proof_top_down))
        return val_hash, proof_bottom_up

    @classmethod
    def verify_proof(cls, key: bytes, val_hash: bytes, root: bytes, proof: List[bytes]) -> bool:
        """
        Verifies inclusion proof bottom-up from leaf to root.
        """
        cls._init_default_hashes()
        key_hash = hashlib.sha256(key).digest()
        bits = cls._to_bits(key_hash)
        
        current = val_hash

        # Step bottom-up: depth_idx 0 corresponds to bit 255 (leaf)
        for i in range(256):
            bit_index = 255 - i
            sibling = proof[i]
            
            if bits[bit_index] == '0':
                current = cls._hash_node(current, sibling)
            else:
                current = cls._hash_node(sibling, current)

        return current == root


# -------------------------------------------------------------------------
# Verification Runner
# -------------------------------------------------------------------------

if __name__ == "__main__":
    smt = SparseMerkleTree()

    key = b"account_0x1"
    val = b"balance_500"

    root = smt.update(key, val)
    val_hash, proof = smt.create_proof(key)

    valid = SparseMerkleTree.verify_proof(key, val_hash, root, proof)
    print(f"Proof Verification: {'SUCCESS' if valid else 'FAILED'}")
