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
    _enforce_primary_facet_evidence,
    validate_grounding,
)
from racevault.retrieval.models import SearchFilters
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

    def resolve_scopes(self, query: str, filters: object) -> tuple[SearchFilters, ...]:
        del query, filters
        return self.response.resolved_scopes or tuple(
            SearchFilters(championship=championship)
            for championship in self.response.resolved_championships
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


def test_validate_grounding_rejects_an_omitted_requested_facet() -> None:
    answer = GeneratedAnswer(
        answer=(
            GeneratedStatement(
                text="The dimensions are specified.",
                citations=("E1",),
                facet_id="F1",
            ),
        ),
        conflicts=(),
        limitations=(),
        insufficient_evidence=False,
    )

    try:
        validate_grounding(
            answer,
            valid_evidence_ids={"E1"},
            required_facet_ids={"F1", "F2"},
        )
    except GroundingValidationError as error:
        assert "omits requested facets" in str(error)
    else:
        raise AssertionError("omitted facet was accepted")


def test_validate_grounding_rejects_unacknowledged_facet_limitation() -> None:
    answer = GeneratedAnswer(
        answer=(
            GeneratedStatement(
                text="The dimensions are specified.",
                citations=("E1",),
                facet_id="F1",
            ),
        ),
        conflicts=(),
        limitations=(
            GeneratedStatement(
                text="The pressure is not established.",
                citations=("E1",),
                facet_id="F2",
            ),
        ),
        insufficient_evidence=False,
    )

    try:
        validate_grounding(
            answer,
            valid_evidence_ids={"E1"},
            required_facet_ids={"F1", "F2"},
        )
    except GroundingValidationError as error:
        assert "require insufficient_evidence" in str(error)
    else:
        raise AssertionError("unacknowledged limitation was accepted")


def test_unlisted_comparison_strips_model_invented_facet_ids() -> None:
    query = (
        "Compare the qualifying-lap requirements in the 2026 PCC Great Britain "
        "and PCC Asia regulations. Address both championships separately before "
        "summarising the differences."
    )
    retrieval = FakeRetrieval(retrieval_response(query))
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=tuple(
                GeneratedStatement(
                    text=f"Grounded comparison statement {index}.",
                    citations=("E1",),
                    facet_id=f"F{index}",
                )
                for index in range(1, 10)
            ),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(GroundedAnswerRequest(query=query))

    assert ollama.generate_count == 1
    assert response.answer.startswith("Grounded comparison statement 1 [E1].")
    assert "F1" not in response.answer
    assert ollama.system_prompt is not None
    assert "Never invent F-numbers" in ollama.system_prompt
    assert "reserve at least one answer statement" in ollama.system_prompt


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
    assert retrieval.requests[0].options.rerank_limit == 20
    assert retrieval.requests[0].options.result_limit == 20
    assert retrieval.released is True
    assert ollama.user_prompt is not None
    assert "BEGIN E1" in ollama.user_prompt
    assert "Joker Tyre definition." in ollama.user_prompt
    assert ollama.system_prompt is not None
    assert "Give a direct conclusion first" in ollama.system_prompt
    assert "Synthesize related facts across passages" in ollama.system_prompt


def test_compound_question_runs_facet_searches_and_prompts_for_coverage(
) -> None:
    query = (
        "For the 992.1 N3 and N3R tyres, build a practical operating summary "
        "covering tyre dimensions, recommended wheel widths, minimum cold "
        "pressures, shoulder-temperature balance, and what recommendation "
        "applies at unlisted tracks."
    )
    retrieval = FakeRetrieval(retrieval_response(query))
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=tuple(
                GeneratedStatement(
                    text=f"Supported result for facet {index}.",
                    citations=("E1",),
                    facet_id=f"F{index}",
                )
                for index in range(1, 6)
            ),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(answer_max_query_facets=6),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(GroundedAnswerRequest(query=query))

    assert len(retrieval.requests) == 6
    assert retrieval.requests[0].query == query
    assert retrieval.requests[1].query.endswith(
"992.1 n3 n3r tyre dimension"
    )
    assert retrieval.requests[-1].query.endswith(
        "992.1 n3 n3r recommendation apply unlisted track"
    )
    assert all(
        item.options.result_limit == 8 for item in retrieval.requests[1:]
    )
    assert ollama.user_prompt is not None
    assert "F1: tyre dimensions" in ollama.user_prompt
    assert "F5: recommendation applies at unlisted tracks" in ollama.user_prompt
    assert "explicitly answer every facet" in ollama.user_prompt
    assert response.answer.startswith("Tyre dimensions — Supported result")
    assert "Minimum cold pressures — Supported result" in response.answer


def test_persistently_omitted_facet_becomes_an_explicit_limitation() -> None:
    query = (
        "Compare the PCC Great Britain and PCC Asia regulations, covering "
        "qualifying format, starting procedures, and track-limits penalties"
    )
    retrieval = FakeRetrieval(retrieval_response(query))
    incomplete = GeneratedAnswer(
        answer=(
            GeneratedStatement(
                text="The qualifying format is established.",
                citations=("E1",),
                facet_id="F1",
            ),
            GeneratedStatement(
                text="The starting procedure is established.",
                citations=("E1",),
                facet_id="F2",
            ),
        ),
        conflicts=(),
        limitations=(),
        insufficient_evidence=False,
    )
    ollama = FakeOllama(incomplete)
    service = GroundedAnswerService(
        settings=Settings(answer_max_query_facets=6),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(GroundedAnswerRequest(query=query))

    assert ollama.generate_count == 2
    assert ollama.system_prompt is not None
    assert "answer omits requested facets: ['F3']" in ollama.system_prompt
    assert response.insufficient_evidence is True
    assert response.limitations == (
        "Track-limits penalties — The model could not produce a validated "
        "result for this requested area from the retrieved evidence [E1].",
    )


def test_comparison_facet_searches_preserve_scopes_and_exclude_foreign_series(
) -> None:
    query = (
        "Compare the PCC Great Britain and PCC Asia regulations, covering "
        "qualifying format, starting procedures, and track-limits penalties"
    )
    base_response = retrieval_response(query)
    base = base_response.results[0]
    scoped_results = tuple(
        base.model_copy(
            update={
                "rank": rank,
                "evidence_text": f"{scope} rule evidence.",
                "source_metadata": {"championship": scope},
                "citation": base.citation.model_copy(
                    update={
                        "chunk_id": f"chk_{rank:032x}",
                        "source_sha256": str(rank) * 64,
                    }
                ),
            }
        )
        for rank, scope in enumerate(
            ("PCC Great Britain", "PCC Asia", "PCC Australia"),
            start=1,
        )
    )
    retrieval = FakeRetrieval(
        base_response.model_copy(
            update={
                "resolved_championships": (
                    "PCC Great Britain",
                    "PCC Asia",
                ),
                "results": scoped_results,
            }
        )
    )
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=tuple(
                GeneratedStatement(
                    text=f"Supported comparison for facet {index}.",
                    citations=("E1", "E2"),
                    facet_id=f"F{index}",
                )
                for index in range(1, 4)
            ),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(answer_max_query_facets=6),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(GroundedAnswerRequest(query=query))

    assert [item.query for item in retrieval.requests] == [
        "PCC Great Britain PCC Asia qualifying format",
        "PCC Great Britain PCC Asia starting procedure",
        "PCC Great Britain PCC Asia track limit penalty",
    ]
    assert all(item.options.channel_limit == 20 for item in retrieval.requests)
    assert all(item.options.fusion_limit == 12 for item in retrieval.requests)
    assert all(item.options.rerank_limit == 4 for item in retrieval.requests)
    assert all(item.options.result_limit == 4 for item in retrieval.requests)
    assert {
        item.source_metadata["championship"] for item in response.evidence
    } == {"PCC Great Britain", "PCC Asia"}


def test_primary_facet_evidence_replaces_a_general_result_at_the_limit() -> None:
    base_response = retrieval_response("tyre summary")
    base = base_response.results[0]
    candidates = tuple(
        base.model_copy(
            update={
                "rank": rank,
                "evidence_text": f"Evidence {rank}",
                "citation": base.citation.model_copy(
                    update={"chunk_id": f"chk_{rank:032x}"}
                ),
            }
        )
        for rank in range(1, 5)
    )
    facet_response = base_response.model_copy(
        update={"results": (candidates[3],)}
    )

    enforced = _enforce_primary_facet_evidence(
        candidates[:3],
        candidates=candidates,
        facet_responses=(facet_response,),
        limit=3,
    )

    assert [item.rank for item in enforced] == [1, 2, 4]


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
    assert "unknown evidence identifiers: ['E2']" in ollama.system_prompt


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


def test_weak_evidence_skips_generation_at_calibrated_threshold() -> None:
    retrieval = FakeRetrieval(retrieval_response("weak match"))
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=(GeneratedStatement(text="unused", citations=("E1",)),),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(answer_minimum_reranker_score=0.95),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(GroundedAnswerRequest(query="weak match"))

    assert response.insufficient_evidence is True
    assert len(response.evidence) == 1
    assert response.evidence_selection is not None
    assert response.evidence_selection.reason == "below_calibrated_threshold"
    assert ollama.generated is False


def test_missing_comparison_scope_skips_generation() -> None:
    base_response = retrieval_response("race rules")
    result = base_response.results[0].model_copy(
        update={"source_metadata": {"championship": "PCC Asia"}}
    )
    retrieval = FakeRetrieval(
        base_response.model_copy(
            update={
                "resolved_championships": (
                    "PCC Great Britain",
                    "PCC Asia",
                ),
                "results": (result,),
            }
        )
    )
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=(GeneratedStatement(text="unused", citations=("E1",)),),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(
        GroundedAnswerRequest(
            query="Race rule differences between Great Britain and Asia"
        )
    )

    assert response.insufficient_evidence is True
    assert response.evidence_selection is not None
    assert response.evidence_selection.reason == "missing_required_scope"
    assert response.limitations == ("Missing evidence for: PCC Great Britain",)
    assert ollama.generated is False


def test_broad_comparison_requests_a_specific_rule_area() -> None:
    base_response = retrieval_response("race rules")
    base_result = base_response.results[0]
    results = (
        base_result.model_copy(
                update={
                    "rank": 1,
                    "evidence_text": "Great Britain qualifying requirement.",
                    "source_metadata": {"championship": "PCC Great Britain"},
                }
        ),
        base_result.model_copy(
                update={
                    "rank": 2,
                    "evidence_text": "Asia restart procedure.",
                    "source_metadata": {"championship": "PCC Asia"},
                "citation": base_result.citation.model_copy(
                    update={"chunk_id": f"chk_{2:032x}"}
                ),
            }
        ),
    )
    retrieval = FakeRetrieval(
        base_response.model_copy(
            update={
                "resolved_championships": (
                    "PCC Great Britain",
                    "PCC Asia",
                ),
                "results": results,
            }
        )
    )
    ollama = FakeOllama(
        GeneratedAnswer(
            answer=(GeneratedStatement(text="unused", citations=("E1",)),),
            conflicts=(),
            limitations=(),
            insufficient_evidence=False,
        )
    )
    service = GroundedAnswerService(
        settings=Settings(),
        retrieval=retrieval,
        ollama=ollama,
    )

    response = service.answer(
        GroundedAnswerRequest(
            query="Race rule differences between Great Britain and Asia"
        )
    )

    assert response.insufficient_evidence is True
    assert response.evidence_selection is not None
    assert response.evidence_selection.reason == "comparison_topic_too_broad"
    assert response.limitations == (
        "Specify a rule area such as starts, qualifying, track limits, "
        "penalties, tyres, or points.",
    )
    assert ollama.generated is False
