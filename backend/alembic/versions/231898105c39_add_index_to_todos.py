"""add index to todos

Revision ID: 231898105c39
Revises: a0790c76a129
Create Date: 2026-09-20 13:45:30.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '231898105c39'
down_revision = 'a0790c76a129'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # We create a composite index on (user_id, completed, created_at DESC)
    # This optimizes queries that filter by user_id and optionally completed,
    # and order by created_at DESC
    op.create_index('ix_todos_user_id_completed_created_at', 'todos', ['user_id', 'completed', sa.text('created_at DESC')])
    op.create_index('ix_todos_user_id_created_at', 'todos', ['user_id', sa.text('created_at DESC')])


def downgrade() -> None:
    op.drop_index('ix_todos_user_id_created_at', table_name='todos')
    op.drop_index('ix_todos_user_id_completed_created_at', table_name='todos')
