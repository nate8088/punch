"""Add address and phone to clients

Revision ID: 0002_add_client_address_phone
Revises: 0001_initial_schema
Create Date: 2026-05-01 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0002_add_client_address_phone'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(32), nullable=True))


def downgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_column('phone')
        batch_op.drop_column('address')