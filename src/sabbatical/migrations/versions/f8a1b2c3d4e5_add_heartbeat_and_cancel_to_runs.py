"""add_heartbeat_and_cancel_to_runs

Revision ID: f8a1b2c3d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-03-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('runs', sa.Column('last_heartbeat', sa.String(), nullable=True))
    op.add_column('runs', sa.Column('cancel_requested', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('runs', 'cancel_requested')
    op.drop_column('runs', 'last_heartbeat')
