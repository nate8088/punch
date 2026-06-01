"""Add per-client invoice email templates

Revision ID: 0007_email_templates
Revises: 0006_long_running_timer
Create Date: 2026-05-31 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0007_email_templates'
down_revision = '0006_long_running_timer'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('invoice_email_subject', sa.Text(), nullable=True))
    op.add_column('clients', sa.Column('invoice_email_body', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('clients', 'invoice_email_body')
    op.drop_column('clients', 'invoice_email_subject')
