"""Quality, latency, and storage gate for experimental visual retrieval."""

from __future__ import annotations

from pydantic import Field

from racevault.evaluation.models import MetricInterval
from racevault.extraction.models import ArtifactModel

COLQWEN_MODEL_ID = "vidore/colqwen2.5-v0.2"
COLQWEN_MODEL_REVISION = "6f6fcdf"


class VisualRetrievalDiagnostics(ArtifactModel):
    page_image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    visual_rank: int = Field(ge=1)
    maxsim_score: float
    model_id: str = COLQWEN_MODEL_ID
    model_revision: str = COLQWEN_MODEL_REVISION


class VisualGateInput(ArtifactModel):
    text_ndcg_at_10: float = Field(ge=0, le=1)
    fused_ndcg_at_10: float = Field(ge=0, le=1)
    improvement_interval: MetricInterval
    added_latency_p95_seconds: float = Field(ge=0)
    index_size_gb: float = Field(ge=0)
    query_count: int = Field(ge=1)


class VisualGateDecision(ArtifactModel):
    enabled: bool
    reasons: tuple[str, ...]


def evaluate_visual_gate(value: VisualGateInput) -> VisualGateDecision:
    reasons = []
    improvement = value.fused_ndcg_at_10 - value.text_ndcg_at_10
    if value.query_count < 40:
        reasons.append("visual slice contains fewer than 40 queries")
    if improvement < 0.05:
        reasons.append("nDCG@10 improvement is below five absolute points")
    if value.improvement_interval.low <= 0:
        reasons.append("95% confidence interval does not exclude zero")
    if value.added_latency_p95_seconds >= 3:
        reasons.append("added p95 latency is not below three seconds")
    if value.index_size_gb >= 8:
        reasons.append("visual index is not below eight gigabytes")
    return VisualGateDecision(enabled=not reasons, reasons=tuple(reasons))
