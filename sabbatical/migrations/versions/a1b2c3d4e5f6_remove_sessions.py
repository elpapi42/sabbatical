"""remove_sessions

Revision ID: a1b2c3d4e5f6
Revises: d47fbc9edd39
Create Date: 2026-03-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd47fbc9edd39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop sessions and session_messages tables."""
    # Use IF EXISTS to handle databases that were created after sessions were removed
    op.execute("DROP TABLE IF EXISTS session_messages")
    op.execute("DROP TABLE IF EXISTS sessions")


def downgrade() -> None:
    """Recreate sessions and session_messages tables."""
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_scope', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('consumed_input_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('consumed_output_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_cost', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('created_at', sa.String(), server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"), nullable=False),
        sa.ForeignKeyConstraint(['organization_scope'], ['organizations.name'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'session_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.String(), server_default=sa.text("(strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now'))"), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')"),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
