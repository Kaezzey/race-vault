"""Immutable experiment fingerprints and runtime resource measurements."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path

from racevault.evaluation.models import ExperimentFingerprint


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_value(repo_root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", "-C", str(repo_root), *arguments),
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def create_experiment_fingerprint(
    *,
    repo_root: Path,
    dataset_path: Path,
    configuration: object,
    model_revisions: dict[str, str],
    random_seed: int,
) -> ExperimentFingerprint:
    commit_sha = _git_value(repo_root, "rev-parse", "HEAD") or "unknown"
    status = _git_value(repo_root, "status", "--porcelain")
    hardware = {
        "machine": platform.machine() or "unknown",
        "processor": platform.processor() or "unknown",
        "cpu_count": str(os.cpu_count() or "unknown"),
    }
    gpu_name = os.environ.get("RACEVAULT_BENCHMARK_GPU_NAME")
    if gpu_name:
        hardware["gpu"] = gpu_name
    return ExperimentFingerprint(
        run_id=str(uuid.uuid4()),
        commit_sha=commit_sha,
        dirty_worktree=bool(status),
        dataset_sha256=file_sha256(dataset_path),
        configuration_sha256=canonical_sha256(configuration),
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        hardware=hardware,
        random_seed=random_seed,
        model_revisions=model_revisions,
    )
