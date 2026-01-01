"""change status column from enum to varchar

Revision ID: a8b9c0d1e2f3
Revises: 6139c39c8c5e
Create Date: 2025-12-30 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = '6139c39c8c5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change status column from enum to varchar."""
    # Change column type from enum to varchar
    op.execute("""
        ALTER TABLE jobprocessingstatus 
        ALTER COLUMN status TYPE VARCHAR(50) 
        USING status::text
    """)


def downgrade() -> None:
    """Revert status column back to enum."""
    op.execute("""
        ALTER TABLE jobprocessingstatus 
        ALTER COLUMN status TYPE jobprocessingstatusenum 
        USING status::jobprocessingstatusenum
    """)

