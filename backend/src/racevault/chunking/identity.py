"""Stable identities shared by chunk consumers."""

from __future__ import annotations

import hashlib

from racevault.chunking.models import ChunkingArtifact
from racevault.extraction.io import canonical_json_bytes


def chunk_artifact_identity(artifact: ChunkingArtifact) -> str:
    identity = (
        artifact.provenance.extraction_sha256.encode()
        + canonical_json_bytes(artifact.provenance.settings)
    )
    return hashlib.sha256(identity).hexdigest()
