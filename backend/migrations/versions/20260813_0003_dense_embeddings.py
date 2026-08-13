"""Add model-versioned dense embeddings.

Revision ID: 20260813_0003
Revises: 20260813_0002
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision = "20260813_0003"
down_revision = "20260813_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("source_role", sa.String(length=128), nullable=True)
    )
    op.create_index("ix_documents_source_role", "documents", ["source_role"])

    op.add_column(
        "chunks",
        sa.Column(
            "artifact_id",
            sa.String(length=64),
            server_default="",
            nullable=False,
        ),
    )
    op.execute("UPDATE chunks SET artifact_id = extraction_sha256")
    op.alter_column("chunks", "artifact_id", server_default=None)
    op.drop_constraint("uq_chunks_extraction_ordinal", "chunks", type_="unique")
    op.create_unique_constraint(
        "uq_chunks_artifact_ordinal",
        "chunks",
        ["document_id", "artifact_id", "ordinal"],
    )
    op.create_index("ix_chunks_artifact_id", "chunks", ["artifact_id"])

    op.create_table(
        "chunk_embeddings",
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=256), nullable=False),
        sa.Column("model_revision", sa.String(length=64), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("dimensions", sa.SmallInteger(), nullable=False),
        sa.Column("normalized", sa.Boolean(), nullable=False),
        sa.Column("embedding", VECTOR(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dimensions = 1024", name="ck_chunk_embeddings_dimensions"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["chunks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("chunk_id", "model_id", "model_revision"),
    )
    op.create_index(
        "ix_chunk_embeddings_cosine_hnsw",
        "chunk_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    op.create_index(
        "ix_chunk_embeddings_model",
        "chunk_embeddings",
        ["model_id", "model_revision"],
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_embeddings_model", table_name="chunk_embeddings")
    op.drop_index(
        "ix_chunk_embeddings_cosine_hnsw", table_name="chunk_embeddings"
    )
    op.drop_table("chunk_embeddings")

    op.drop_index("ix_chunks_artifact_id", table_name="chunks")
    op.drop_constraint("uq_chunks_artifact_ordinal", "chunks", type_="unique")
    op.create_unique_constraint(
        "uq_chunks_extraction_ordinal",
        "chunks",
        ["document_id", "extraction_sha256", "ordinal"],
    )
    op.drop_column("chunks", "artifact_id")

    op.drop_index("ix_documents_source_role", table_name="documents")
    op.drop_column("documents", "source_role")
