"""Deterministic, inspectable evidence selection for grounded generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from racevault.api.models import RetrievalResult
from racevault.generation.models import EvidenceSelectionDiagnostics

QueryIntent = Literal["concept", "exact_or_numeric", "comparison_or_conflict"]

_TOKEN = re.compile(r"[a-z0-9]+")
_IDENTIFIER = re.compile(r"\b(?=[a-z0-9._/-]*[a-z])(?=[a-z0-9._/-]*\d)[a-z0-9._/-]+\b")
_NUMBER_WITH_UNIT = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|kg|g|nm|n·m|bar|psi|kpa|mpa|°c|c|v|a|%)\b"
)
_CLAUSE_NUMBER = re.compile(r"\b\d+(?:\.\d+)+\b")
# Words that introduce an enumeration, so what follows them is a list of
# topics rather than one topic that happens to contain a comma.
_LIST_MARKER = re.compile(
    r"\b(?:addressing|covering|including|such as|namely|specifically)\b",
    re.IGNORECASE,
)
_SEPARATOR = re.compile(r"\s*(?:,\s*(?:and\s+|or\s+)?|;)\s*", re.IGNORECASE)
_CONJUNCTION = re.compile(r"\s+(?:and|or|as well as|plus)\s+", re.IGNORECASE)
_BETWEEN = re.compile(r"\bbetween\b", re.IGNORECASE)
_COMPARISON_TERMS = frozenset(
    {
        "compare",
        "comparison",
        "conflict",
        "difference",
        "differences",
        "differ",
        "disagree",
        "revision",
        "revisions",
        "versus",
        "vs",
        "changed",
    }
)
_COMPARISON_FILLER_TERMS = _COMPARISON_TERMS | frozenset(
    {
        "and",
        "are",
        "between",
        "do",
        "does",
        "for",
        "from",
        "how",
        "in",
        "is",
        "of",
        "the",
        "what",
        "which",
        "with",
    }
)
_GENERIC_RULE_TERMS = frozenset(
    {"race", "racing", "regulation", "regulations", "rule", "rules"}
)
_QUANTITATIVE_TERMS = frozenset(
    {
        "capacity",
        "dimension",
        "dimensions",
        "distance",
        "maximum",
        "minimum",
        "pressure",
        "pressures",
        "temperature",
        "temperatures",
        "torque",
        "weight",
        "width",
        "widths",
    }
)
_TOPIC_STOP_TERMS = _COMPARISON_FILLER_TERMS | _GENERIC_RULE_TERMS | frozenset(
    {
        "about",
        "all",
        "at",
        "can",
        "could",
        "explain",
        "give",
        "i",
        "me",
        "please",
        "tell",
        "that",
        "this",
        "to",
    }
)


@dataclass(frozen=True)
class EvidenceSelection:
    """Selected evidence plus the auditable decision made by the controller."""

    results: tuple[RetrievalResult, ...]
    diagnostics: EvidenceSelectionDiagnostics
    sufficient: bool


@dataclass(frozen=True)
class QueryFacet:
    """One explicit subtopic requested in a compound user question."""

    facet_id: str
    label: str
    retrieval_query: str
    evidence_target: int = 1


def _singular(word: str) -> str:
    """Fold a regular English plural, so "pressures" and "pressure" agree."""

    if len(word) > 3 and word.endswith("ies"):
        return f"{word[:-3]}y"
    if len(word) > 4 and word.endswith("sses"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _is_plural(text: str) -> bool:
    return any(_singular(word) != word for word in _TOKEN.findall(text.casefold()))


def _content_terms(text: str) -> tuple[str, ...]:
    """Return the topic-bearing words of a phrase, singular and in order."""

    return tuple(
        singular
        for word in _TOKEN.findall(text.casefold())
        if (singular := _singular(word)) not in _TOPIC_STOP_TERMS
        and word not in _TOPIC_STOP_TERMS
    )


def _split_conjunction(text: str) -> tuple[str, ...]:
    """Split "A and B" only where both sides carry a topic of their own.

    A bare conjunction joins two topics ("tyre pressures and camber settings")
    about as often as it joins one ("the inside and outside shoulder", "front
    and rear"). Requiring a substantial phrase on each side separates the two,
    and a preceding "between" marks a comparison rather than a list.
    """

    for match in _CONJUNCTION.finditer(text):
        left, right = text[: match.start()], text[match.end() :]
        if _BETWEEN.search(left):
            continue
        if len(_content_terms(left)) >= 2 and len(_content_terms(right)) >= 2:
            return (left, *_split_conjunction(right))
    return (text,)


def _clean(part: str) -> str:
    """Trim a split fragment, dropping any interrogative stem it inherited.

    Splitting "What are the tyre pressures and camber settings" leaves the
    question stem on the first part only. Removing it keeps the facet labels
    parallel, which matters because they are shown beside the answer.
    """

    part = " ".join(part.split()).strip(" ,;:.-?!")
    without_stem = _clean(_QUESTION_STEM.sub("", part)) if _QUESTION_STEM.match(
        part
    ) else part
    return without_stem or part


_QUESTION_STEM = re.compile(
    r"^(?:what|which|how|when|where|who|why)"
    r"(?:\s+(?:is|are|was|were|do|does|did))?"
    r"(?:\s+the)?\s+",
    re.IGNORECASE,
)


def decompose_query_facets(
    query: str,
    *,
    maximum_facets: int = 6,
) -> tuple[QueryFacet, ...]:
    """Split a compound question into independently retrievable subtopics.

    A facet gets its own hybrid search, so a question that asks for several
    things is not answered from whichever subtopic happened to dominate one
    ranked list. Decomposition stays deterministic and syntactic: it reads the
    structure of the question and never rewrites its vocabulary, leaving
    terminology to the search-time synonym graph, which covers every query
    rather than the phrasings someone happened to test.

    Callers should pass the query with metadata scope terms already removed, so
    that "between PCC Asia and PCC France" cannot look like a list of topics.
    """

    marker = _LIST_MARKER.search(query)
    listed = query[marker.end() :] if marker else query
    subject = query[: marker.start()] if marker else query

    groups = tuple(part for part in _SEPARATOR.split(listed) if _clean(part))
    if marker is not None:
        # Inside an explicit list, "A, B and C" and "A and B" both enumerate.
        parts = tuple(
            part for group in groups for part in _split_conjunction(group)
        )
    elif classify_query_intent(query) == "comparison_or_conflict":
        # "Compare the 2025 and 2026 regulations" joins the two sides of one
        # comparison. Only an explicit list marker overrides that reading.
        return ()
    elif len(groups) > 2:
        parts = groups
    else:
        parts = _split_conjunction(listed)

    parts = tuple(cleaned for part in parts if (cleaned := _clean(part)))
    if not 2 <= len(parts) <= maximum_facets:
        return ()
    if any(not _content_terms(part) for part in parts):
        # A fragment with no topic of its own is punctuation, not a facet.
        return ()

    # Part numbers, model codes, and clause references name what the question
    # is about, and each facet search needs them even when only the subject
    # mentioned them.
    anchors = tuple(
        dict.fromkeys(
            (
                *_CLAUSE_NUMBER.findall(subject.casefold()),
                *_IDENTIFIER.findall(subject.casefold()),
            )
        )
    )
    # Two or more named entities mean a plural facet needs one passage each,
    # but only while the evidence budget can seat them all.
    targets_allowed = len(anchors) >= 2 and len(parts) <= 4

    facets = []
    for index, label in enumerate(parts, start=1):
        # Anchors are added back to every facet, so removing them from the
        # label first stops "992.2" also arriving as the tokens "992" and "2".
        stripped = label
        for anchor in anchors:
            stripped = re.sub(re.escape(anchor), " ", stripped, flags=re.IGNORECASE)
        focus = (*anchors, *_content_terms(stripped))
        facets.append(
            QueryFacet(
                facet_id=f"F{index}",
                label=label,
                retrieval_query=" ".join(focus),
                evidence_target=2 if targets_allowed and _is_plural(label) else 1,
            )
        )
    return tuple(facets)




def classify_query_intent(query: str) -> QueryIntent:
    """Classify only signals that have deterministic retrieval implications."""

    normalized = query.casefold()
    tokens = set(_TOKEN.findall(normalized))
    if tokens & _COMPARISON_TERMS:
        return "comparison_or_conflict"
    if (
        '"' in query
        or _IDENTIFIER.search(normalized)
        or _NUMBER_WITH_UNIT.search(normalized)
        or _CLAUSE_NUMBER.search(normalized)
        or tokens & _QUANTITATIVE_TERMS
    ):
        return "exact_or_numeric"
    return "concept"


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN.findall(text.casefold()))


def _topic_tokens(text: str) -> frozenset[str]:
    """Normalize small wording variations that should match the same facet."""

    return frozenset(_singular(token) for token in _tokens(text))


def _similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _relevance(result: RetrievalResult, intent: QueryIntent) -> float:
    score = result.diagnostics.reranker_score
    if intent == "exact_or_numeric" and result.diagnostics.lexical_rank is not None:
        score += 0.05 / result.diagnostics.lexical_rank
    return score


def _topic_coverage(
    result: RetrievalResult,
    topic_terms: frozenset[str],
) -> float:
    """Measure how much of the question's meaningful vocabulary is present."""

    if not topic_terms:
        return 0.0
    citation = result.citation
    searchable = " ".join(
        (
            result.evidence_text,
            citation.source_filename,
            *citation.section_path,
            citation.clause_reference or "",
        )
    )
    return len(topic_terms & _topic_tokens(searchable)) / len(topic_terms)


def _query_relevance(
    result: RetrievalResult,
    intent: QueryIntent,
    topic_terms: frozenset[str],
    topic_weight: float,
) -> float:
    return _relevance(result, intent) + topic_weight * _topic_coverage(
        result, topic_terms
    )


def _scope(result: RetrievalResult) -> str | None:
    value = result.source_metadata.get("championship")
    return value if isinstance(value, str) and value else None


def _rim_dimension_key(result: RetrievalResult) -> str | None:
    """Return a value-agnostic rim width/diameter key when one is present."""

    match = re.search(
        r"\b(\d{1,2}(?:\.\d+)?)\s*j\s*(?:x\s*)?"
        r"(\d{1,2}(?:\.\d+)?)\b",
        result.evidence_text.casefold(),
    )
    if match is None:
        return None
    return f"{match.group(1)}j{match.group(2)}"


def _comparison_topic_is_too_broad(
    query: str,
    required_scopes: tuple[str, ...],
) -> bool:
    if len(required_scopes) < 2:
        return False
    scope_tokens = {
        token
        for scope in required_scopes
        for token in _TOKEN.findall(scope.casefold())
    }
    content_tokens = (
        set(_TOKEN.findall(query.casefold()))
        - scope_tokens
        - _COMPARISON_FILLER_TERMS
    )
    return not content_tokens or content_tokens <= _GENERIC_RULE_TERMS


def select_evidence(
    query: str,
    candidates: tuple[RetrievalResult, ...],
    *,
    limit: int,
    required_scopes: tuple[str, ...] = (),
    requested_facets: tuple[QueryFacet, ...] = (),
    facet_candidate_ids: dict[str, tuple[str, ...]] | None = None,
    topic_weight: float = 0.15,
    diversity_weight: float = 0.25,
    duplicate_threshold: float = 0.9,
    max_per_source: int = 2,
    minimum_reranker_score: float | None = None,
) -> EvidenceSelection:
    """Select relevant, non-redundant evidence without invoking another model.

    Required scopes are represented first. Remaining slots use a small MMR-style
    objective. The original retrieval rank is restored before evidence IDs are
    assigned so the external ordering remains intuitive.
    """

    intent = classify_query_intent(query)
    topic_terms = _topic_tokens(query) - _TOPIC_STOP_TERMS
    if not candidates or limit <= 0:
        diagnostics = EvidenceSelectionDiagnostics(
            policy="facet_topic_mmr_scope_v3",
            query_intent=intent,
            candidates_considered=len(candidates),
            selected_count=0,
            duplicates_removed=0,
            distinct_sources=0,
            required_scopes=required_scopes,
            covered_scopes=(),
            requested_facets=tuple(facet.label for facet in requested_facets),
            covered_facets=(),
            missing_facets=tuple(facet.label for facet in requested_facets),
            maximum_reranker_score=None,
            minimum_score_threshold=minimum_reranker_score,
            sufficient=False,
            reason="no_candidates",
        )
        return EvidenceSelection((), diagnostics, False)

    maximum_score = max(item.diagnostics.reranker_score for item in candidates)
    score_sufficient = (
        minimum_reranker_score is None
        or maximum_score >= minimum_reranker_score
    )

    selected: list[RetrievalResult] = []
    selected_tokens: list[frozenset[str]] = []
    source_counts: dict[str, int] = {}
    duplicate_ids: set[str] = set()

    def add(item: RetrievalResult, *, enforce_source_cap: bool = True) -> bool:
        item_tokens = _tokens(item.evidence_text)
        is_duplicate = any(
            _similarity(item_tokens, existing) >= duplicate_threshold
            for existing in selected_tokens
        )
        if is_duplicate:
            duplicate_ids.add(item.citation.chunk_id)
            return False
        source = item.citation.source_sha256
        if enforce_source_cap and source_counts.get(source, 0) >= max_per_source:
            return False
        selected.append(item)
        selected_tokens.append(item_tokens)
        source_counts[source] = source_counts.get(source, 0) + 1
        return True

    # Scope coverage and balance are hard constraints for explicit cross-series
    # questions. Fill the scopes round-robin before using the general MMR pool.
    scope_passes = 1 if required_scopes else 0
    for scope_pass in range(scope_passes):
        for scope in required_scopes:
            scoped = [
                item
                for item in candidates
                if _scope(item) == scope and item not in selected
            ]
            scoped.sort(
                key=lambda item: (
                    -_query_relevance(
                        item, intent, topic_terms, topic_weight
                    ),
                    item.rank,
                )
            )
            for item in scoped:
                if add(item, enforce_source_cap=scope_pass > 0):
                    break
            if len(selected) >= limit:
                break
        if len(selected) >= limit:
            break

    # Explicit multi-part questions need at least one strongly topic-matched
    # passage per facet. Source concentration is intentionally relaxed here:
    # one authoritative manual may contain every requested subtopic.
    facet_terms = {
        facet.label: _topic_tokens(facet.label) - _TOPIC_STOP_TERMS
        for facet in requested_facets
    }
    candidates_by_facet = facet_candidate_ids or {}
    for facet in requested_facets:
        terms = facet_terms[facet.label]
        preferred_ids = candidates_by_facet.get(facet.label, ())
        if not terms:
            continue
        # A comparison needs evidence for this facet from every named scope,
        # not merely generic balance somewhere in the final evidence set.
        for scope in required_scopes:
            if len(selected) >= limit:
                break
            if any(
                item.citation.chunk_id in preferred_ids
                and _scope(item) == scope
                for item in selected
            ):
                continue
            scoped_preferred = [
                item
                for item in candidates
                if item not in selected
                and item.citation.chunk_id in preferred_ids
                and _scope(item) == scope
            ]
            scoped_preferred.sort(
                key=lambda item: (
                    -_topic_coverage(item, terms),
                    preferred_ids.index(item.citation.chunk_id),
                )
            )
            for item in scoped_preferred:
                if add(item, enforce_source_cap=False):
                    break
        rejected: set[str] = set()
        while len(selected) < limit:
            if preferred_ids:
                covered_count = sum(
                    item.citation.chunk_id in preferred_ids for item in selected
                )
            else:
                covered_count = sum(
                    _topic_coverage(item, terms) >= 0.5 for item in selected
                )
            if covered_count >= facet.evidence_target:
                break
            preferred_pool = [
                item
                for item in candidates
                if item not in selected
                and item.citation.chunk_id in preferred_ids
                and item.citation.chunk_id not in rejected
            ]
            facet_pool = (
                preferred_pool
                if preferred_ids
                else [
                    item
                    for item in candidates
                    if item not in selected
                    and item.citation.chunk_id not in rejected
                ]
            )
            if not facet_pool:
                break
            if preferred_pool:
                preferred_rank = {
                    chunk_id: index
                    for index, chunk_id in enumerate(preferred_ids)
                }
                ranking_pool = preferred_pool
                if "pressure" in terms:
                    selected_rims = {
                        rim
                        for item in selected
                        if (rim := _rim_dimension_key(item)) is not None
                    }
                    unseen_rim_pool = [
                        item
                        for item in preferred_pool
                        if _rim_dimension_key(item) not in selected_rims
                    ]
                    ranking_pool = unseen_rim_pool or preferred_pool
                ranked = sorted(
                    ranking_pool,
                    key=lambda item: (
                        -_topic_coverage(item, terms),
                        preferred_rank[item.citation.chunk_id],
                    ),
                )
            else:
                ranked = sorted(
                    facet_pool,
                    key=lambda item: (
                        -_topic_coverage(item, terms),
                        -_relevance(item, classify_query_intent(facet.label)),
                        item.rank,
                    ),
                )
            best = ranked[0]
            if preferred_pool or _topic_coverage(best, terms) > 0:
                if not add(best, enforce_source_cap=False):
                    rejected.add(best.citation.chunk_id)
            else:
                break

    # For compound questions, the independently reranked facet passages are
    # the evidence budget. Adding general MMR filler reintroduces adjacent table
    # rows and unrelated regulations that can confuse a small local generator.
    pool = (
        []
        if requested_facets
        else [item for item in candidates if item not in selected]
    )
    while pool and len(selected) < limit:
        if intent == "comparison_or_conflict" and selected:
            selected_sources = {
                item.citation.source_sha256 for item in selected
            }
            unseen_source_pool = [
                item
                for item in pool
                if item.citation.source_sha256 not in selected_sources
            ]
            scoring_pool = unseen_source_pool or pool
        else:
            scoring_pool = pool
        scored: list[tuple[float, int, RetrievalResult]] = []
        for item in scoring_pool:
            item_tokens = _tokens(item.evidence_text)
            novelty_penalty = max(
                (_similarity(item_tokens, existing) for existing in selected_tokens),
                default=0.0,
            )
            utility = _query_relevance(
                item, intent, topic_terms, topic_weight
            ) - diversity_weight * novelty_penalty
            scored.append((utility, -item.rank, item))
        best = max(scored, key=lambda value: (value[0], value[1]))[2]
        pool.remove(best)
        add(best)

    selected.sort(key=lambda item: item.rank)
    covered = tuple(
        scope
        for scope in required_scopes
        if any(_scope(item) == scope for item in selected)
    )
    coverage_sufficient = len(covered) == len(required_scopes)
    covered_facets = tuple(
        facet.label
        for facet in requested_facets
        if facet_terms[facet.label]
        and any(
            _topic_coverage(item, facet_terms[facet.label]) >= 0.5
            or item.citation.chunk_id
            in candidates_by_facet.get(facet.label, ())
            for item in selected
        )
    )
    missing_facets = tuple(
        facet.label
        for facet in requested_facets
        if facet.label not in covered_facets
    )
    reason: Literal[
        "selected",
        "below_calibrated_threshold",
        "missing_required_scope",
        "comparison_topic_too_broad",
    ]
    if not score_sufficient:
        reason = "below_calibrated_threshold"
    elif not coverage_sufficient:
        reason = "missing_required_scope"
    elif _comparison_topic_is_too_broad(query, required_scopes):
        reason = "comparison_topic_too_broad"
    else:
        reason = "selected"
    sufficient = reason == "selected"
    diagnostics = EvidenceSelectionDiagnostics(
        policy="facet_topic_mmr_scope_v3",
        query_intent=intent,
        candidates_considered=len(candidates),
        selected_count=len(selected),
        duplicates_removed=len(duplicate_ids),
        distinct_sources=len({item.citation.source_sha256 for item in selected}),
        required_scopes=required_scopes,
        covered_scopes=covered,
        requested_facets=tuple(facet.label for facet in requested_facets),
        covered_facets=covered_facets,
        missing_facets=missing_facets,
        maximum_reranker_score=maximum_score,
        minimum_score_threshold=minimum_reranker_score,
        sufficient=sufficient,
        reason=reason,
    )
    return EvidenceSelection(tuple(selected), diagnostics, sufficient)
