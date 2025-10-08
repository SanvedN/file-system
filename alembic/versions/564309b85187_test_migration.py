"""test migration

Revision ID: 564309b85187
Revises: 58f79584900e
Create Date: 2025-10-08 13:58:31.113568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '564309b85187'
down_revision: Union[str, Sequence[str], None] = '58f79584900e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
