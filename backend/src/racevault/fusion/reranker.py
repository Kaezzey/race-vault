"""Local BGE cross-encoder reranking."""

from __future__ import annotations

import importlib
import math
from collections.abc import Sequence
from typing import Any, Protocol

from racevault.fusion.models import FusedCandidate, RerankerSpec


class CandidateReranker(Protocol):
    @property
    def spec(self) -> RerankerSpec: ...

    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]: ...


class BgeReranker:
    """Score query-passage pairs with the pinned BGE reranker."""

    def __init__(
        self,
        *,
        spec: RerankerSpec | None = None,
        device: str = "auto",
        batch_size: int = 4,
        local_files_only: bool = False,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._spec = spec or RerankerSpec()
        self._batch_size = batch_size
        try:
            self._torch: Any = importlib.import_module("torch")
            self._transformers: Any = importlib.import_module("transformers")
        except ImportError as error:
            raise RuntimeError(
                "BGE reranking requires the semantic dependencies; "
                "install the project with [semantic]"
            ) from error
        self._device = self._resolve_device(device)
        self._local_files_only = local_files_only
        self._tokenizer: Any = None
        self._model: Any = None

    @property
    def spec(self) -> RerankerSpec:
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
        self._tokenizer = self._transformers.AutoTokenizer.from_pretrained(
            self._spec.model_id,
            revision=self._spec.model_revision,
            local_files_only=self._local_files_only,
        )
        classifier: Any = self._transformers.AutoModelForSequenceClassification
        self._model = classifier.from_pretrained(
            self._spec.model_id,
            revision=self._spec.model_revision,
            dtype=dtype,
            local_files_only=self._local_files_only,
        )
        self._model.to(self._device)
        self._model.eval()

    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]:
        if not query.strip():
            raise ValueError("reranker query must contain text")
        if not passages:
            return ()
        if any(not passage.strip() for passage in passages):
            raise ValueError("reranker passages must contain text")
        self._load_model()

        scores: list[float] = []
        for start in range(0, len(passages), self._batch_size):
            batch = list(passages[start : start + self._batch_size])
            encoded = self._tokenizer(
                [query] * len(batch),
                batch,
                padding=True,
                truncation=True,
                max_length=self._spec.max_tokens,
                return_tensors="pt",
            )
            encoded = {name: value.to(self._device) for name, value in encoded.items()}
            with self._torch.inference_mode():
                logits = self._model(**encoded).logits.reshape(-1).float()
                values = (
                    self._torch.sigmoid(logits)
                    if self._spec.normalized_scores
                    else logits
                )
            scores.extend(float(value) for value in values.cpu().tolist())
        valid = len(scores) == len(passages) and all(
            math.isfinite(item) for item in scores
        )
        if not valid:
            raise RuntimeError("reranker returned invalid scores")
        return tuple(scores)


def rerank_candidates(
    query: str,
    candidates: tuple[FusedCandidate, ...],
    *,
    reranker: CandidateReranker,
    limit: int,
) -> tuple[FusedCandidate, ...]:
    selected = candidates[:limit]
    scores = reranker.score(query, [item.contextual_text for item in selected])
    if len(scores) != len(selected):
        raise RuntimeError("reranker returned an unexpected score count")
    scored = [
        candidate.model_copy(update={"reranker_score": score})
        for candidate, score in zip(selected, scores, strict=True)
    ]
    ordered = sorted(
        scored,
        key=lambda item: (
            -(item.reranker_score if item.reranker_score is not None else 0.0),
            -item.rrf_score,
            item.chunk_id,
        ),
    )
    return tuple(
        item.model_copy(update={"final_rank": rank})
        for rank, item in enumerate(ordered, start=1)
    )
