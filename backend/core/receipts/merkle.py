"""Merkle tree primitives for daily receipt-root computation
(Wave 95).

The tree is the textbook duplicate-last-leaf binary sha256: pairs at
each level are concatenated as raw bytes (NOT hex strings) and
hashed; if a level has an odd number of nodes, the last node is
duplicated. The root is the hex sha256 of the final pair.

For an empty list the root is ``""`` (empty string) so the daily
``MerkleRoot`` row is unambiguous when no receipts were emitted.
"""

from __future__ import annotations

import hashlib
from typing import Any


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def compute_root(receipt_hashes: list[str]) -> str:
    """Compute the Merkle root over the given receipt hashes.

    Hashes must be lowercase hex (the format ``chain.compute_hash``
    produces). Returns the root as 64-char hex, or ``""`` for an
    empty list.
    """

    if not receipt_hashes:
        return ""
    layer = [bytes.fromhex(h) for h in receipt_hashes]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [_h(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0].hex()


async def daily_root(day_iso: str, store: Any) -> str:
    """Compute (or fetch cached) the Merkle root for ``day_iso``.

    ``store`` is a :class:`backend.core.receipts.store.ReceiptStore`.
    If a row already exists in ``merkle_roots`` we return that;
    otherwise we replay the day's NDJSON, compute the root, and
    insert+return it.
    """

    cached = await store.get_merkle_root(day_iso)
    if cached is not None:
        return cached.root_hex
    receipts = await store.replay_chain_for_day(day_iso)
    hashes = [r.hash for r in receipts]
    root_hex = compute_root(hashes)
    await store.upsert_merkle_root(
        day_iso=day_iso,
        root_hex=root_hex,
        leaf_count=len(hashes),
    )
    return root_hex


def proof(receipt_hashes: list[str], leaf_index: int) -> dict[str, Any]:
    """Generate a Merkle proof path for ``leaf_index``.

    Returns ``{"leaf": "<hex>", "path": [{"sibling": "<hex>",
    "side": "left"|"right"}, ...], "root": "<hex>"}``.
    Path is bottom-up; each step gives the sibling hash and the side
    on which the sibling sits relative to the current node, so a
    verifier can recompute the parent as
    ``sha256(node + sibling)`` if side=="right" or
    ``sha256(sibling + node)`` if side=="left".
    """

    if not receipt_hashes:
        raise ValueError("cannot build proof for empty list")
    if leaf_index < 0 or leaf_index >= len(receipt_hashes):
        raise ValueError(
            f"leaf_index {leaf_index} out of range 0..{len(receipt_hashes)}"
        )
    leaf_hex = receipt_hashes[leaf_index]
    path: list[dict[str, str]] = []
    layer = [bytes.fromhex(h) for h in receipt_hashes]
    idx = leaf_index
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        # find sibling
        if idx % 2 == 0:
            sibling = layer[idx + 1]
            side = "right"
        else:
            sibling = layer[idx - 1]
            side = "left"
        path.append({"sibling": sibling.hex(), "side": side})
        layer = [_h(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
        idx //= 2
    return {"leaf": leaf_hex, "path": path, "root": layer[0].hex()}


def verify_proof(
    leaf_hex: str, path: list[dict[str, str]], root_hex: str
) -> bool:
    """Replay ``path`` from ``leaf_hex`` and check it lands on ``root_hex``.

    Useful for callers / clients verifying a proof out-of-band.
    """

    cur = bytes.fromhex(leaf_hex)
    for step in path:
        sib = bytes.fromhex(step["sibling"])
        if step.get("side") == "left":
            cur = _h(sib + cur)
        else:
            cur = _h(cur + sib)
    return cur.hex() == root_hex
