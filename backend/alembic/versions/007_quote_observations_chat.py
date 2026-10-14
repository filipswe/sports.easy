"""Retain price observations and shared chat quota reservations."""

import sqlalchemy as sa
from alembic import op

revision = "007_observations"
down_revision = "006_crests"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quote_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fixture_kickoff", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("quote_id", "observed_at"),
    )
    op.create_index("ix_quote_observations_quote_id", "quote_observations", ["quote_id"])
    op.create_table(
        "usage_counters",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_counters_expires_at", "usage_counters", ["expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE TRIGGER immutable_quote_observations BEFORE UPDATE OR DELETE ON quote_observations FOR EACH ROW EXECUTE FUNCTION reject_research_mutation()"
        )


def downgrade():
    op.drop_table("usage_counters")
    op.drop_table("quote_observations")
