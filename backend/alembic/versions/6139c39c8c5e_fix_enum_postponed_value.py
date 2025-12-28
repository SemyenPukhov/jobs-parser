"""fix enum postponed value

Revision ID: 6139c39c8c5e
Revises: 28bb05929320
Create Date: 2025-12-29 00:34:32.404176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6139c39c8c5e'
down_revision: Union[str, None] = '28bb05929320'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    bind.execute(sa.text("COMMIT"))
    bind.execute(sa.text("ALTER TYPE jobprocessingstatusenum ADD VALUE IF NOT EXISTS 'Postponed'"))


def downgrade() -> None:
    """Downgrade schema."""
    pass
