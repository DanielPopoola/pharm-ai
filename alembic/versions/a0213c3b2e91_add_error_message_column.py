"""add error_message column

Revision ID: a0213c3b2e91
Revises: 24c19f4934d7
Create Date: 2026-06-06 03:23:21.593141

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a0213c3b2e91'
down_revision: Union[str, Sequence[str], None] = '24c19f4934d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TABLE ingestion_jobs ADD COLUMN error_message TEXT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE ingestion_jobs DROP COLUMN error_message")
