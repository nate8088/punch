"""Add long-running timer support

Revision ID: 0006_add_long_running_timer_support
Revises: 0005_add_audit_log
Create Date: 2026-05-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '0006_long_running_timer'
down_revision = '0005_add_audit_log'
branch_labels = None
depends_on = None


def upgrade():
    # Track whether a long-running timer notification has been sent for
    # this entry. NULL = not notified. Stamped when the email goes out.
    op.add_column(
        'time_entries',
        sa.Column('long_running_notified_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column('time_entries', 'long_running_notified_at')
