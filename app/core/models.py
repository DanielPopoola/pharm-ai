import uuid

from sqlalchemy import ARRAY, TIMESTAMP, Column, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Drug(Base):
    __tablename__ = "drugs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drug_name = Column(Text, nullable=False, unique=True)
    brand_names = Column(ARRAY(Text))
    therapeutic_class = Column(Text)
    source_url = Column(Text)
    ingested_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class DrugChunk(Base):
    __tablename__ = "drug_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drug_id = Column(UUID(as_uuid=True), ForeignKey("drugs.id", ondelete="CASCADE"))
    drug_name = Column(Text, nullable=False)
    section_type = Column(Text, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(
        Text, nullable=True
    )  # treated as raw text; vector ops done in raw SQL
    ingested_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drug_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    triggered_by = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
