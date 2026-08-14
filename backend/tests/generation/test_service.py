from __future__ import annotations

from racevault.api.models import RetrievalSearchRequest, RetrievalSearchResponse
from racevault.config import Settings
from racevault.generation.models import (
    GeneratedAnswer,
    GeneratedStatement,
    GenerationModelIdentity,
    GenerationStatus,
    GenerationUsage,
    GroundedAnswerRequest,
)
from racevault.generation.ollama import OllamaGeneration
from racevault.generation.service import (
    GroundedAnswerService,
    GroundingValidationError,
    validate_grounding,
)
from tests.api.factories import retrieval_response


class FakeRetrieval:
    def __init__(self, response: RetrievalSearchResponse) -> None:
        self.response = response
        self.requests: list[RetrievalSearchRequest] = []
        self.released = False

    def search(self, request: RetrievalSearchRequest) -> RetrievalSearchResponse:
        self.requests.append(request)
        return self.response.model_copy(
            update={"query": request.query, "filters": request.filters}
        )

    def release_models(self) -> None:
        self.released = True


class FakeOllama:
    def __init__(
        self,
        answer: GeneratedAnswer | tuple[GeneratedAnswer, ...],
    ) -> None:
        self.generated_answers = (
            answer if isinstance(answer, tuple) else (answer,)
        )
        self.system_prompt: str | None = None
        self.user_prompt: str | None = None
        self.generated = False
        self.generate_count = 0

    def status(self) -> GenerationStatus:
        return GenerationStatus(
            available=True,
            ollama_version="0.32.9",
            model=GenerationModelIdentity(
                model="qwen3.5:9b",
                digest="a" * 64,
                parameter_size="9.7B",
                quantization_level="Q4_K_M",
            ),
            capabilities=("completion",),
        )

    def generate(
        self, *, system_prompt: str, user_prompt: str
    ) -> OllamaGeneration:
        self.generated = True
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        answer = self.generated_answers[
            min(self.generate_count, len(self.generated_answers) - 1)
        ]
        self.generate_count += 1
        return OllamaGeneration(
            answer=answer,
            model=self.status().model,
            usage=GenerationUsage(
                total_duration_ms=10,
                load_duration_ms=5,
                prompt_tokens=100,
                output_tokens=20,
            ),
        )


def test_validate_grounding_rejects_unknown_citation() -> None:
    answer = GeneratedAnswer(
        answer=(
            GeneratedStatement(
                text="Use the adjustment wheel.",
                citations=("E2",),
            ),
        ),
        conflicts=(),
        limitations=(),
        insufficient_evidence=False,
    )

    try:
        validate_grounding(answer, valid_evidence_ids={"E1"})
    except GroundingValidationError as error:
        assert "unknown evidence" in str(error)
    else:
        raise AssertionError("unknown citation was accepted")


def test_validate_grounding_accepts_statement_level_citations() -> None:
    answer = GeneratedAnswer(
        answer=(
            GeneratedStatement(
                text="The limits depend on the axle.",
                citations=("E1", "E2"),
            ),
        ),
        conflicts=(),
        limitations=(),
        insufficient_evidence=False,
    )

    validate_grounding(answer, valid_evidence_ids={"E1", "E2"})


def test_answer_maps_validated_evidence_to_source_citation() -> None:
    retrieval = FakeRetrieval(retrieval_response("brake balance"))
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=(
                GeneratedStatement(
                    text="Turn the adjustment wheel.",
                    citations=("E1",),
                ),
            ),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(answer_release_retrieval_models=True),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(GroundedAnswerRequest(query="brake balance"))

    assert response.answer == "Turn the adjustment wheel [E1]."
    assert response.citations[0].evidence_id == "E1"
    assert response.citations[0].citation.page_numbers == (6,)
    assert response.evidence[0].evidence_text == "Joker Tyre definition."
    assert retrieval.requests[0].options.result_limit == 10
    assert retrieval.released is True
    assert ollama.user_prompt is not None
    assert "BEGIN E1" in ollama.user_prompt
    assert "Joker Tyre definition." in ollama.user_prompt


def test_answer_includes_one_evidence_item_per_resolved_championship() -> None:
    base_response = retrieval_response("weight comparison")
    base_result = base_response.results[0]
    championships = ("Series A", "Series B", "Series C", "Series D")
    results = tuple(
        base_result.model_copy(
            update={
                "rank": index,
                "evidence_text": f"{championship} weight requirement.",
                "source_metadata": {"championship": championship},
                "citation": base_result.citation.model_copy(
                    update={"chunk_id": f"chk_{index:032x}"}
                ),
            }
        )
        for index, championship in enumerate(championships, start=1)
    )
    retrieval = FakeRetrieval(
        base_response.model_copy(
            update={
                "resolved_championships": championships,
                "results": results,
            }
        )
    )
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=tuple(
                GeneratedStatement(
                    text=f"{championship} has a weight requirement.",
                    citations=(f"E{index}",),
                )
                for index, championship in enumerate(championships, start=1)
            ),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(
            answer_evidence_limit=3,
            answer_max_evidence_limit=10,
        ),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(
        GroundedAnswerRequest(query="compare four series")
    )

    assert len(response.evidence) == 4
    assert [item.source_metadata["championship"] for item in response.evidence] == [
        "Series A",
        "Series B",
        "Series C",
        "Series D",
    ]
    assert ollama.user_prompt is not None
    assert "BEGIN E4" in ollama.user_prompt


def test_answer_retries_one_invalid_evidence_identifier() -> None:
    retrieval = FakeRetrieval(retrieval_response("camber restrictions"))
    ollama = FakeOllama(
        (
            GeneratedAnswer(
                answer=(
                    GeneratedStatement(
                        text="Camber is restricted.",
                        citations=("E2",),
                    ),
                ),
                conflicts=(),
                limitations=(),
                insufficient_evidence=False,
            ),
            GeneratedAnswer(
                answer=(
                    GeneratedStatement(
                        text="Camber is restricted.",
                        citations=("E1",),
                    ),
                ),
                conflicts=(),
                limitations=(),
                insufficient_evidence=False,
            ),
        )
    )
    service = GroundedAnswerService(
        settings=Settings(),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(
        GroundedAnswerRequest(query="camber restrictions")
    )

    assert response.answer == "Camber is restricted [E1]."
    assert response.generation_usage.prompt_tokens == 200
    assert ollama.generate_count == 2
    assert ollama.system_prompt is not None
    assert "previous response failed" in ollama.system_prompt


def test_no_evidence_returns_deterministic_insufficient_response() -> None:
    empty = retrieval_response().model_copy(update={"results": ()})
    retrieval = FakeRetrieval(empty)
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=(
                GeneratedStatement(text="unused", citations=("E1",)),
            ),
            conflicts=(),
            limitations=(),
            insufficient_evidence=True,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(GroundedAnswerRequest(query="unknown item"))

    assert response.insufficient_evidence is True
    assert response.citations == ()
    assert response.generation_usage.output_tokens == 0
    assert ollama.generated is False
