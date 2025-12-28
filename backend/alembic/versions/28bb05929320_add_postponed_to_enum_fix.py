"""add postponed to enum fix

Revision ID: 28bb05929320
Revises: 9c0d9ac1e7f6
Create Date: 2025-12-28 23:36:21.798226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28bb05929320'
down_revision: Union[str, None] = '9c0d9ac1e7f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ADD VALUE cannot run inside a transaction
    op.execute("COMMIT")
    op.execute("ALTER TYPE jobprocessingstatusenum ADD VALUE IF NOT EXISTS 'Postponed'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL doesn't support removing enum values
    pass
