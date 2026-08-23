"""Build the v2 evaluation dataset, verifying every label against the corpus.

Run against a populated database:

    cd evaluation && RACEVAULT_POSTGRES_HOST=localhost python build_dataset.py

Reads the original v1 set from queries-legacy-v1.json, upgrades it to the v2
schema, adds the queries defined below, and writes queries.json.

Every positive label is checked to match a real chunk, and every negative is
checked to have no answer anywhere in the corpus, so the dataset cannot drift
away from what is actually indexed.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "../backend/src")

import psycopg
from psycopg.rows import dict_row

from racevault.config import get_settings
from racevault.evaluation.models import EvaluationDataset

AUS26 = (
    "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-"
    "Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf"
)
AUS25 = (
    "Rules and Regulations/PCC Australia/"
    "2025_Porsche_Carrera_Cup_Australia_Sporting_Technical_Regulations_V1.pdf"
)
ABS_OP = "ABS/Core/Operation_Manual_70618763_ABS_M5_Kit.pdf"
ABS_DS = "ABS/Core/Data_Sheet_70612107_ABS_M5_Kit.pdf"
ECU = "ECU/engine_control_unit_ms_6-x_manual.pdf"
PARTS25 = (
    "Part Catalogues/PA10_0842_911 GT3 Cup MY2021-2025 (Typ 992)"
    "_CW_11_26_English_en.pdf"
)
SWUP = "PMRSI Other/2026-08-10_PA10_1918/992Cup_Manual_Software_Updates_V03.pdf"

# Families group documents that share content, so a query cannot be tuned on
# one split and scored on a near-duplicate in the other.
FAMILY_BY_PREFIX = {
    "Rules and Regulations/PCC Australia/": "pcc-australia-regulations",
    "Rules and Regulations/PCC Asia/": "pcc-asia-regulations",
    "Rules and Regulations/Other/": "pcc-other-regulations",
    "Porsche Technical Manuals/": "porsche-technical-manual",
    "Tyre Data/": "tyre-data",
    "ABS/": "abs-m5",
    "ECU/": "ms6-ecu",
    "Part Catalogues/": "part-catalogue-992",
    "PMRSI Other/": "cup-software-updates",
}

# A family sits wholly in one split. Everything read while authoring labels for
# this dataset is development, because its passages are no longer unseen. The
# legacy queries shipped with the repository and were not consulted, so they
# form the held-out set for changes made since.
SPLIT_BY_FAMILY = {
    "pcc-australia-regulations": "development",
    "abs-m5": "development",
    "ms6-ecu": "development",
    "part-catalogue-992": "development",
    "cup-software-updates": "development",
    "tyre-data": "test",
    "porsche-technical-manual": "test",
    "pcc-asia-regulations": "test",
    "pcc-other-regulations": "test",
}
# Abstention calibration needs unanswerable queries on the development side and
# an untouched set on the other, so the negatives are dealt between the two.
NEGATIVE_SPLIT = {
    "neg_drs_activation": "development",
    "neg_energy_recovery": "development",
    "neg_push_to_pass": "development",
    "neg_success_ballast": "development",
    "neg_budget_cap": "test",
    "neg_turbo_boost_limit": "test",
    "neg_sprint_shootout": "test",
    "neg_rallycross_joker": "test",
}
LEGACY_SLICES = {
    "regulation_definition": ("regulation",),
    "regulation_rule": ("regulation",),
    "regulation_concept": ("regulation",),
    "regulation_table": ("regulation", "table"),
    "technical_table": ("table", "numeric_unit"),
    "technical_recommendation": ("numeric_unit",),
    "manual_concept": ("technical_manual",),
    "manual_procedure": ("technical_manual", "ordered_steps"),
    "manual_safety": ("technical_manual", "safety_limit"),
    "wrong_revision": ("adversarial", "superseded_edition"),
    "multi_source_conflict": ("adversarial", "conflict"),
}


def label(path, page, *contains, grade=3, label_id=None):
    item = {
        "source_path": path,
        "page_number": page,
        "text_contains": list(contains),
        "relevance_grade": grade,
    }
    if label_id:
        item["label_id"] = label_id
    return item


def negative(query_id, query):
    return {
        "query_id": query_id,
        "query": query,
        "category": "out_of_corpus",
        "split": NEGATIVE_SPLIT[query_id],
        "slices": ["negative"],
        "expected_empty": True,
    }


# The evaluation runner calls the fusion pipeline directly, so it does not
# perform the service-level scope resolution that turns an unqualified question
# into a championship and season filter. These queries therefore carry the
# filters that resolution would have produced, and measure retrieval *within*
# the resolved scope. That resolution itself is covered by
# tests/retrieval/test_scope_resolution.py.
AUS_CURRENT = {"championship": "PCC Australia", "season": 2026}
AUS_PREVIOUS = {"championship": "PCC Australia", "season": 2025}

NEW_QUERIES = [
    # --- Edition and recency -------------------------------------------------
    # The 2025 and 2026 Australian editions give different answers to all of
    # these, and renumber the clauses that carry them.
    {
        "query_id": "aus_current_minimum_weight",
        "query": "What is the minimum weight of the car in Carrera Cup Australia?",
        "category": "regulation_rule",
        "split": "test",
        "slices": ["regulation", "numeric_unit", "current_edition"],
        "document_family": "pcc-australia-regulations",
        "filters": AUS_CURRENT,
        "relevant": [label(AUS26, 26, "minimum of 1300 kg")],
    },
    {
        "query_id": "aus_current_racing_weight",
        "query": "What minimum racing weight must a Carrera Cup Australia car achieve?",
        "category": "regulation_rule",
        "split": "test",
        "slices": ["regulation", "numeric_unit", "current_edition"],
        "document_family": "pcc-australia-regulations",
        "filters": AUS_CURRENT,
        "relevant": [label(AUS26, 26, "1385 kg")],
    },
    {
        "query_id": "aus_2025_minimum_weight",
        "query": (
            "What was the minimum car weight in the 2025 Carrera Cup Australia "
            "regulations?"
        ),
        "category": "regulation_rule",
        "split": "test",
        "slices": ["regulation", "numeric_unit", "superseded_edition"],
        "document_family": "pcc-australia-regulations",
        "filters": AUS_PREVIOUS,
        "relevant": [label(AUS25, 47, "1295 kg")],
    },
    {
        "query_id": "aus_driver_minimum_weight",
        "query": (
            "How much must a driver weigh in Carrera Cup Australia, and what "
            "happens if they weigh less?"
        ),
        "category": "regulation_rule",
        "split": "test",
        "slices": ["regulation", "numeric_unit", "current_edition"],
        "document_family": "pcc-australia-regulations",
        "filters": AUS_CURRENT,
        "relevant": [label(AUS26, 26, "85 kg", "ballast")],
    },
    {
        "query_id": "aus_fuel_remaining",
        "query": "How much fuel must remain in the car during a track session?",
        "category": "regulation_rule",
        "split": "test",
        "slices": ["regulation", "numeric_unit"],
        "document_family": "pcc-australia-regulations",
        "filters": AUS_CURRENT,
        "relevant": [label(AUS26, 19, "2.0 kg of fuel")],
    },
    {
        "query_id": "aus_driver_age",
        "query": "How old must a driver be to compete in Carrera Cup Australia?",
        "category": "regulation_rule",
        "split": "test",
        "slices": ["regulation", "current_edition"],
        "document_family": "pcc-australia-regulations",
        "filters": AUS_CURRENT,
        "relevant": [label(AUS26, 9, "seventeen (17) years of age")],
    },
    {
        "query_id": "aus_joker_tyre_allocation",
        "query": "How many Joker Tyres may a driver use per round and per season?",
        "category": "regulation_rule",
        "split": "test",
        "slices": ["regulation", "numeric_unit"],
        "document_family": "pcc-australia-regulations",
        "filters": AUS_CURRENT,
        "relevant": [label(AUS26, 17, "six (6) front", "two (2) front")],
    },
    # --- Component manuals: 1584 chunks, previously unrepresented ------------
    {
        "query_id": "abs_map_switch_torque",
        "query": "What tightening torque applies to the ABS map switch?",
        "category": "component_specification",
        "split": "development",
        "slices": ["component_manual", "numeric_unit", "safety_limit"],
        "document_family": "abs-m5",
        "relevant": [label(ABS_OP, 21, "1 to 2 Nm")],
    },
    {
        "query_id": "abs_brake_line_diameter",
        "query": "What brake line should be used to plumb the ABS M5 unit?",
        "category": "component_specification",
        "split": "development",
        "slices": ["component_manual", "numeric_unit"],
        "document_family": "abs-m5",
        "relevant": [label(ABS_OP, 22, "3.3 mm")],
    },
    {
        "query_id": "abs_reset_after_drive_cycle_fault",
        "query": "How is the ABS reset after a drive cycle fault?",
        "category": "component_procedure",
        "split": "development",
        "slices": ["component_manual", "ordered_steps"],
        "document_family": "abs-m5",
        "relevant": [label(ABS_OP, 37, "Power off - Power on")],
    },
    {
        "query_id": "abs_map_switch_positions",
        "query": "How many positions does the ABS function switch have?",
        "category": "component_specification",
        "split": "development",
        "slices": ["component_manual", "numeric_unit"],
        "document_family": "abs-m5",
        "relevant": [
            label(ABS_OP, 31, "12-position map switch"),
            label(ABS_DS, 2, "12-position function switch", grade=2),
        ],
    },
    {
        "query_id": "abs_hydraulic_unit_weight",
        "query": "How much does the ABS M5 hydraulic unit weigh?",
        "category": "technical_table",
        "split": "development",
        "slices": ["component_manual", "table", "numeric_unit"],
        "document_family": "abs-m5",
        "relevant": [label(ABS_DS, 2, "1,910 g")],
    },
    {
        "query_id": "software_update_order",
        "query": "In what order must the PowerBox, logger and display be updated?",
        "category": "component_procedure",
        "split": "development",
        "slices": ["component_manual", "ordered_steps"],
        "document_family": "cup-software-updates",
        "relevant": [
            label(SWUP, 20, "Update firmware PowerBox", "Update firmware display")
        ],
    },
    # --- Engineering reference: 164 chunks, previously unrepresented ---------
    {
        "query_id": "ecu_temperature_range",
        "query": "What temperature range is the MS 6 harness connector rated for?",
        "category": "technical_table",
        "split": "development",
        "slices": ["engineering_reference", "table", "numeric_unit"],
        "document_family": "ms6-ecu",
        "relevant": [label(ECU, 74, "Temperature range")],
    },
    {
        "query_id": "ecu_flywheel_sensor_type",
        "query": "Can the MS 6 use an inductive sensor for flywheel measurement?",
        "category": "component_specification",
        "split": "development",
        "slices": ["engineering_reference", "exact_identifier"],
        "document_family": "ms6-ecu",
        "relevant": [label(ECU, 29, "flywheel measurement")],
    },
    # --- Part catalogue: 360 chunks, previously unrepresented ----------------
    {
        "query_id": "part_front_left_caliper",
        "query": (
            "What is the part number for the front left brake caliper on the "
            "992 GT3 Cup?"
        ),
        "category": "exact_identifier",
        "split": "development",
        "slices": ["part_catalogue", "table", "exact_identifier"],
        "document_family": "part-catalogue-992",
        "relevant": [label(PARTS25, 109, "9F1615427D")],
    },
    # --- Negatives: each topic verified absent from the whole corpus ---------
    negative("neg_drs_activation", "Where are the DRS activation zones?"),
    negative(
        "neg_energy_recovery",
        "How is the energy recovery system deployed on a qualifying lap?",
    ),
    negative(
        "neg_push_to_pass",
        "How many push to pass activations does each driver get?",
    ),
    negative(
        "neg_success_ballast", "How much success ballast is added after a race win?"
    ),
    negative("neg_budget_cap", "What is the budget cap for the season?"),
    negative(
        "neg_turbo_boost_limit",
        "What is the maximum turbocharger boost pressure permitted?",
    ),
    negative("neg_sprint_shootout", "What is the sprint shootout format?"),
    negative("neg_rallycross_joker", "How does the rallycross joker lap work?"),
]

# Terms whose total absence from the corpus makes each negative genuine.
NEGATIVE_ABSENT_TERMS = {
    "neg_drs_activation": ("DRS", "drag reduction system"),
    "neg_energy_recovery": ("energy recovery", "hybrid deployment"),
    "neg_push_to_pass": ("push to pass",),
    "neg_success_ballast": ("success ballast",),
    "neg_budget_cap": ("budget cap",),
    "neg_turbo_boost_limit": ("turbocharger boost",),
    "neg_sprint_shootout": ("sprint shootout",),
    "neg_rallycross_joker": ("rallycross",),
}


def family_for(source_path: str) -> str:
    normalized = source_path.replace("\\", "/")
    for prefix, family in FAMILY_BY_PREFIX.items():
        if normalized.casefold().startswith(prefix.casefold()):
            return family
    raise ValueError(f"no document family for {source_path}")


def upgrade_legacy(query: dict) -> dict:
    """Move a v1 query onto the v2 schema without changing what it asserts."""

    families = {family_for(item["source_path"]) for item in query.get("relevant", ())}
    if len(families) > 1:
        # A cross-document query belongs to whichever family it is scored on
        # first; recording several would let it straddle both splits.
        family = sorted(families)[0]
    else:
        family = next(iter(families), None)
    upgraded = dict(query)
    upgraded["document_family"] = family
    upgraded["split"] = SPLIT_BY_FAMILY.get(family, "development")
    upgraded["slices"] = list(LEGACY_SLICES.get(query["category"], ()))
    for item in upgraded.get("relevant", ()):
        item.setdefault("relevance_grade", 3)
    return upgraded


def verify(queries: list[dict]) -> list[str]:
    settings = get_settings()
    failures: list[str] = []
    with psycopg.connect(settings.psycopg_conninfo, row_factory=dict_row) as conn:
        for query in queries:
            for item in query.get("relevant", ()):
                page = item.get("page_number")
                rows = conn.execute(
                    """
                    SELECT c.evidence_text
                    FROM chunks c JOIN documents d ON d.id = c.document_id
                    WHERE lower(d.source_path) = lower(%s)
                      AND (%s::smallint IS NULL
                           OR c.page_numbers @> ARRAY[%s]::smallint[])
                    """,
                    (item["source_path"], page, page),
                ).fetchall()
                matched = any(
                    all(
                        value.casefold() in row["evidence_text"].casefold()
                        for value in item["text_contains"]
                    )
                    for row in rows
                )
                if not matched:
                    failures.append(
                        f"{query['query_id']}: no chunk on "
                        f"{item['source_path']} p{page} contains "
                        f"{item['text_contains']} ({len(rows)} chunks on that page)"
                    )
            for term in NEGATIVE_ABSENT_TERMS.get(query["query_id"], ()):
                found = conn.execute(
                    "SELECT count(*) AS n FROM chunks WHERE evidence_text ILIKE %s",
                    (f"%{term}%",),
                ).fetchone()["n"]
                if found:
                    failures.append(
                        f"{query['query_id']}: {term!r} appears in {found} chunks, "
                        "so the query is not a true negative"
                    )
    return failures


def main() -> int:
    root = pathlib.Path(__file__).parent
    legacy = json.loads(
        (root / "queries-legacy-v1.json").read_text(encoding="utf-8")
    )
    queries = [upgrade_legacy(item) for item in legacy["queries"]] + NEW_QUERIES
    for query in queries:
        family = query.get("document_family")
        if family:
            query["split"] = SPLIT_BY_FAMILY[family]

    failures = verify(queries)
    for line in failures:
        print("FAIL", line)
    if failures:
        return 1

    dataset = EvaluationDataset.model_validate(
        {
            "schema_name": "racevault.retrieval_evaluation",
            "schema_version": 2,
            "dataset_id": "racevault-corpus-v2",
            "dataset_version": "2.0.0",
            "queries": queries,
        }
    )
    (root / "queries.json").write_text(
        json.dumps(dataset.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    positives = [item for item in dataset.queries if not item.expected_empty]
    print(
        f"wrote {len(dataset.queries)} queries "
        f"({len(positives)} positive, {len(dataset.queries) - len(positives)} negative)"
    )
    for split in ("development", "test"):
        chosen = [item for item in dataset.queries if item.split == split]
        print(f"  {split}: {len(chosen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
