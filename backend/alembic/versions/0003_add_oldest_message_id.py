"""add oldest_message_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11 14:27:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('source_groups', sa.Column('oldest_message_id', sa.BigInteger(), nullable=True))

def downgrade() -> None:
    op.drop_column('source_groups', 'oldest_message_id')
