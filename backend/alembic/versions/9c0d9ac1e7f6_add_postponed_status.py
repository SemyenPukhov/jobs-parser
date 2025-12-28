"""add postponed status

Revision ID: 9c0d9ac1e7f6
Revises: 77d30efe11ae
Create Date: 2025-12-28 21:23:37.588399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c0d9ac1e7f6'
down_revision: Union[str, None] = '77d30efe11ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ADD VALUE cannot run inside a transaction
    # Must commit current transaction first
    op.execute("COMMIT")
    op.execute("ALTER TYPE jobprocessingstatusenum ADD VALUE IF NOT EXISTS 'Postponed'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL doesn't support removing enum values directly
    # Would need to recreate the type, which is complex
    pass
