"""Create provenance-linked chunks.

Revision ID: 20260813_0002
Revises: 20260812_0001
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0002"
down_revision = "20260812_0001"
branch_labels = None
depends_on = None

chunk_strategy = postgresql.ENUM(
    "clause",
    "section_evidence",
    "page_table",
    "hierarchical_passage",
    "generic_evidence",
    name="chunk_strategy",
    create_type=False,
)

chunk_kind = postgresql.ENUM(
    "clause",
    "section",
    "passage",
    "table",
    "page",
    "evidence",
    name="chunk_kind",
    create_type=False,
)


def upgrade() -> None:
    chunk_strategy.create(op.get_bind(), checkfirst=True)
    chunk_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("extraction_sha256", sa.String(length=64), nullable=False),
        sa.Column("strategy", chunk_strategy, nullable=False),
        sa.Column("kind", chunk_kind, nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("contextual_text", sa.Text(), nullable=False),
        sa.Column("contextual_sha256", sa.String(length=64), nullable=False),
        sa.Column("section_path", postgresql.JSONB(), nullable=False),
        sa.Column("clause_reference", sa.String(length=128), nullable=True),
        sa.Column("page_start", sa.SmallInteger(), nullable=False),
        sa.Column("page_end", sa.SmallInteger(), nullable=False),
        sa.Column("page_numbers", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column(
            "element_ids", postgresql.ARRAY(sa.String(length=35)), nullable=False
        ),
        sa.Column("table_ids", postgresql.ARRAY(sa.String(length=36)), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("oversize", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "character_count > 0", name="ck_chunks_character_count_positive"
        ),
        sa.CheckConstraint("page_end >= page_start", name="ck_chunks_page_range"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "extraction_sha256",
            "ordinal",
            name="uq_chunks_extraction_ordinal",
        ),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_kind", "chunks", ["kind"])
    op.create_index("ix_chunks_strategy", "chunks", ["strategy"])
    op.create_index("ix_chunks_page_range", "chunks", ["page_start", "page_end"])


def downgrade() -> None:
    op.drop_index("ix_chunks_page_range", table_name="chunks")
    op.drop_index("ix_chunks_strategy", table_name="chunks")
    op.drop_index("ix_chunks_kind", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    chunk_kind.drop(op.get_bind(), checkfirst=True)
    chunk_strategy.drop(op.get_bind(), checkfirst=True)
