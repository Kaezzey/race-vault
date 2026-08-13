"""Local BGE-M3 dense embedding adapter."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any, Protocol

from racevault.semantic.models import DenseVector, EmbeddingModelSpec


class DenseEmbedder(Protocol):
    @property
    def spec(self) -> EmbeddingModelSpec: ...

    def encode(self, texts: Sequence[str]) -> tuple[DenseVector, ...]: ...


class BgeM3Embedder:
    """Generate normalized CLS embeddings with the pinned BGE-M3 model."""

    def __init__(
        self,
        *,
        spec: EmbeddingModelSpec | None = None,
        device: str = "auto",
        batch_size: int = 8,
        local_files_only: bool = False,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._spec = spec or EmbeddingModelSpec()
        self._batch_size = batch_size
        try:
            torch = importlib.import_module("torch")
            transformers = importlib.import_module("transformers")
        except ImportError as error:
            raise RuntimeError(
                "BGE-M3 requires the semantic dependencies; "
                "install the project with [semantic]"
            ) from error
        self._torch: Any = torch
        self._device = self._resolve_device(device)
        self._transformers: Any = transformers
        self._local_files_only = local_files_only
        self._tokenizer: Any = None
        self._model: Any = None

    @property
    def spec(self) -> EmbeddingModelSpec:
        return self._spec

    @property
    def device(self) -> str:
        return self._device

    def _resolve_device(self, requested: str) -> str:
        if requested == "auto":
            return "cuda" if self._torch.cuda.is_available() else "cpu"
        if requested not in {"cpu", "cuda"}:
            raise ValueError("device must be auto, cpu, or cuda")
        if requested == "cuda" and not self._torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")
        return requested

    def _load_model(self) -> None:
        if self._model is not None:
            return
        dtype = (
            self._torch.float16
            if self._device == "cuda"
            else self._torch.float32
        )
        auto_tokenizer: Any = self._transformers.AutoTokenizer
        auto_model: Any = self._transformers.AutoModel
        self._tokenizer = auto_tokenizer.from_pretrained(
            self._spec.model_id,
            revision=self._spec.model_revision,
            local_files_only=self._local_files_only,
        )
        self._model = auto_model.from_pretrained(
            self._spec.model_id,
            revision=self._spec.model_revision,
            dtype=dtype,
            local_files_only=self._local_files_only,
        )
        self._model.to(self._device)
        self._model.eval()

    def encode(self, texts: Sequence[str]) -> tuple[DenseVector, ...]:
        if not texts:
            return ()
        if any(not text.strip() for text in texts):
            raise ValueError("embedding inputs must contain text")
        self._load_model()

        vectors: list[DenseVector] = []
        functional = self._torch.nn.functional
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self._spec.max_tokens,
                return_tensors="pt",
            )
            encoded = {name: value.to(self._device) for name, value in encoded.items()}
            with self._torch.inference_mode():
                output = self._model(**encoded)
                dense = output.last_hidden_state[:, 0]
                dense = functional.normalize(dense, p=2, dim=1)
            for values in dense.float().cpu().tolist():
                vector = tuple(float(item) for item in values)
                vectors.append(DenseVector(values=vector))
        return tuple(vectors)
