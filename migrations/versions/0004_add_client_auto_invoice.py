"""Add auto_invoice to clients

Revision ID: 0004_add_client_auto_invoice
Revises: 0003_timestamp_with_timezone
Create Date: 2026-05-02 00:04:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0004_add_client_auto_invoice'
down_revision = '0003_timestamp_with_timezone'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auto_invoice', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_column('auto_invoice')