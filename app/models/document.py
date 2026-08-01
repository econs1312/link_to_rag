import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Enum,
    Integer,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.session import Base
from app.core.config import settings


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id = Column(String(36), nullable=False, index=True)
    source_url = Column(Text, nullable=False, index=True)
    source_type = Column(String(50), nullable=True)
    title = Column(Text, nullable=True)
    author = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    cleaned_markdown = Column(Text, nullable=True)
    status = Column(Enum(IngestionStatus), default=IngestionStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    metadata_info = Column(JSON, nullable=True, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("Document", back_populates="chunks")


# Index for pgvector cosine similarity search and fulltext search
Index(
    "idx_document_chunks_embedding",
    DocumentChunk.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
