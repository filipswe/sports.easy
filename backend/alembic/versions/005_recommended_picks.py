"""First half scores and an immutable official recommendation record."""

import sqlalchemy as sa
from alembic import op

revision = "005_picks"
down_revision = "004_immutable"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fixtures", sa.Column("home_half_goals", sa.Integer(), nullable=True))
    op.add_column("fixtures", sa.Column("away_half_goals", sa.Integer(), nullable=True))
    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "fixture_id", sa.String(36), sa.ForeignKey("fixtures.id"), nullable=False, unique=True
        ),
        sa.Column(
            "publication_id", sa.String(36), sa.ForeignKey("publications.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy", sa.String(80), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE TRIGGER immutable_recommendations BEFORE UPDATE OR DELETE ON recommendations FOR EACH ROW EXECUTE FUNCTION reject_research_mutation()"
        )


def downgrade():
    op.drop_table("recommendations")
    op.drop_column("fixtures", "away_half_goals")
    op.drop_column("fixtures", "home_half_goals")
