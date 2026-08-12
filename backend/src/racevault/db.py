"""SQLAlchemy metadata for authoritative RaceVault records."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from racevault.chunking.models import ChunkKind, ChunkStrategy


class Base(DeclarativeBase):
    pass


class DocumentType(enum.StrEnum):
    REGULATION = "regulation"
    TECHNICAL_MANUAL = "technical_manual"
    TYRE_DATA = "tyre_data"
    PART_CATALOGUE = "part_catalogue"
    COMPONENT_MANUAL = "component_manual"
    ENGINEERING_REFERENCE = "engineering_reference"
    UNKNOWN = "unknown"


class SourceAuthority(enum.StrEnum):
    OFFICIAL_REGULATION = "official_regulation"
    MANUFACTURER_DOCUMENT = "manufacturer_document"
    COMPONENT_SUPPLIER_DOCUMENT = "component_supplier_document"
    ENGINEERING_REFERENCE = "engineering_reference"
    TEAM_DOCUMENT = "team_document"
    UNKNOWN = "unknown"


class Document(Base):
    """Registry entry for one immutable source file."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            name="document_type",
            native_enum=True,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=DocumentType.UNKNOWN,
        nullable=False,
    )
    vehicle_generation: Mapped[str | None] = mapped_column(String(64))
    championship: Mapped[str | None] = mapped_column(String(128))
    season: Mapped[int | None] = mapped_column(SmallInteger)
    revision: Mapped[str | None] = mapped_column(String(128))
    authority: Mapped[SourceAuthority] = mapped_column(
        Enum(
            SourceAuthority,
            name="source_authority",
            native_enum=True,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=SourceAuthority.UNKNOWN,
        nullable=False,
    )
    language: Mapped[str | None] = mapped_column(String(16))
    page_count: Mapped[int | None] = mapped_column(Integer)
    extra_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class Chunk(Base):
    """Provenance-linked evidence unit used by retrieval systems."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy: Mapped[ChunkStrategy] = mapped_column(
        Enum(
            ChunkStrategy,
            name="chunk_strategy",
            native_enum=True,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    kind: Mapped[ChunkKind] = mapped_column(
        Enum(
            ChunkKind,
            name="chunk_kind",
            native_enum=True,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    contextual_text: Mapped[str] = mapped_column(Text, nullable=False)
    contextual_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    section_path: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    clause_reference: Mapped[str | None] = mapped_column(String(128))
    page_start: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    page_end: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    page_numbers: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False
    )
    element_ids: Mapped[list[str]] = mapped_column(ARRAY(String(35)), nullable=False)
    table_ids: Mapped[list[str]] = mapped_column(ARRAY(String(36)), nullable=False)
    provenance: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    oversize: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
