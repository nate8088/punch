"""Initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )

    op.create_table('settings',
        sa.Column('key', sa.String(64), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    op.create_table('clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('contact_name', sa.String(128), nullable=True),
        sa.Column('contact_email', sa.String(128), nullable=True),
        sa.Column('billing_mode', sa.String(16), nullable=False),
        sa.Column('retainer_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('retainer_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('overage_rate', sa.Numeric(10, 2), nullable=True),
        sa.Column('hourly_rate', sa.Numeric(10, 2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('invoice_number', sa.String(32), nullable=False),
        sa.Column('invoice_type', sa.String(16), nullable=True),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('line_items', sa.JSON(), nullable=True),
        sa.Column('subtotal', sa.Numeric(10, 2), nullable=True),
        sa.Column('total', sa.Numeric(10, 2), nullable=True),
        sa.Column('status', sa.String(16), nullable=True),
        sa.Column('issued_date', sa.Date(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('paid_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('imported_from', sa.String(64), nullable=True),
        sa.Column('external_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number')
    )

    op.create_table('time_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_billable', sa.Boolean(), nullable=True),
        sa.Column('is_overage', sa.Boolean(), nullable=True),
        sa.Column('imported_from', sa.String(64), nullable=True),
        sa.Column('external_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('time_entries')
    op.drop_table('invoices')
    op.drop_table('clients')
    op.drop_table('settings')
    op.drop_table('users')