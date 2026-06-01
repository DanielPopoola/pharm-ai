"""initial_schema

Revision ID: 24c19f4934d7
Revises:
Create Date: 2026-05-31 15:55:00.031199

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "24c19f4934d7"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        CREATE TABLE drugs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            drug_name TEXT NOT NULL,
            brand_names TEXT[],
            therapeutic_class TEXT,
            source_url TEXT,
            ingested_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(drug_name)
        )
    """)

    op.execute("""
        CREATE TABLE drug_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            drug_id UUID REFERENCES drugs(id) ON DELETE CASCADE,
            drug_name TEXT NOT NULL,
            section_type TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(768),
            ingested_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE ingestion_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            drug_name TEXT NOT NULL,
            status TEXT NOT NULL,
            triggered_by TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            completed_at TIMESTAMPTZ
        )
    """)

    op.execute(
        "CREATE INDEX ON drug_chunks USING ivfflat (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ON drugs USING gin(to_tsvector('english', drug_name))")
    op.execute(
        "CREATE INDEX ON drug_chunks USING gin(to_tsvector('english', chunk_text))"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS drug_chunks")
    op.execute("DROP TABLE IF EXISTS drugs")
    op.execute("DROP TABLE IF EXISTS ingestion_jobs")
