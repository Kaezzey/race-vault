"""Shared loading behaviour for local torch models."""

from __future__ import annotations

import importlib
from typing import Any


def import_torch_dependencies() -> tuple[Any, Any]:
    """Import torch and transformers, or explain how to install them."""

    try:
        return (
            importlib.import_module("torch"),
            importlib.import_module("transformers"),
        )
    except ImportError as error:
        raise RuntimeError(
            "local models require the semantic dependencies; "
            "install the project with [semantic]"
        ) from error


def resolve_device(torch: Any, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested not in {"cpu", "cuda"}:
        raise ValueError("device must be auto, cpu, or cuda")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return requested
