"""Create pgvector extension and initial document registry.

Revision ID: 20260812_0001
Revises: None
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260812_0001"
down_revision = None
branch_labels = None
depends_on = None

document_type = postgresql.ENUM(
    "regulation",
    "technical_manual",
    "tyre_data",
    "part_catalogue",
    "component_manual",
    "engineering_reference",
    "unknown",
    name="document_type",
    create_type=False,
)

source_authority = postgresql.ENUM(
    "official_regulation",
    "manufacturer_document",
    "component_supplier_document",
    "engineering_reference",
    "team_document",
    "unknown",
    name="source_authority",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    document_type.create(op.get_bind(), checkfirst=True)
    source_authority.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("vehicle_generation", sa.String(length=64), nullable=True),
        sa.Column("championship", sa.String(length=128), nullable=True),
        sa.Column("season", sa.SmallInteger(), nullable=True),
        sa.Column("revision", sa.String(length=128), nullable=True),
        sa.Column("authority", source_authority, nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256"),
        sa.UniqueConstraint("source_path"),
        sa.CheckConstraint(
            "season IS NULL OR season BETWEEN 1900 AND 2200",
            name="ck_documents_season_range",
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count > 0",
            name="ck_documents_page_count_positive",
        ),
    )
    op.create_index(
        "ix_documents_scope",
        "documents",
        ["vehicle_generation", "championship", "season", "revision"],
    )
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_authority", "documents", ["authority"])


def downgrade() -> None:
    op.drop_index("ix_documents_authority", table_name="documents")
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_scope", table_name="documents")
    op.drop_table("documents")
    source_authority.drop(op.get_bind(), checkfirst=True)
    document_type.drop(op.get_bind(), checkfirst=True)
    # The vector extension is shared infrastructure and is intentionally retained.

