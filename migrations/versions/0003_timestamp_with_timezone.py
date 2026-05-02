"""Convert timestamps to timezone-aware

Revision ID: 0003_timestamp_with_timezone
Revises: fee3ab30ec3c
Create Date: 2026-05-02 00:03:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0003_timestamp_with_timezone'
down_revision = 'fee3ab30ec3c'
branch_labels = None
depends_on = None


def upgrade():
    # Reinterpret existing naive timestamps as UTC without shifting values
    op.execute("ALTER TABLE time_entries ALTER COLUMN started_at TYPE TIMESTAMPTZ USING started_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE time_entries ALTER COLUMN ended_at TYPE TIMESTAMPTZ USING ended_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE time_entries ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE invoices ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE clients ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'")


def downgrade():
    op.execute("ALTER TABLE time_entries ALTER COLUMN started_at TYPE TIMESTAMP USING started_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE time_entries ALTER COLUMN ended_at TYPE TIMESTAMP USING ended_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE time_entries ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE invoices ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE clients ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'")