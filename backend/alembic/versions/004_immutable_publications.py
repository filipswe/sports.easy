"""Protect published versions against SQL updates/deletes on PostgreSQL."""

from alembic import op

revision = "004_immutable"
down_revision = "2c52f53a6102"
branch_labels = None
depends_on = None
TABLES = ["quotes", "predictions", "publications", "settlements", "evaluation_runs"]


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_research_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Research versions are append-only'; END $$"
        )
        for table in TABLES:
            op.execute(
                f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_research_mutation()"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f"DROP TRIGGER immutable_{table} ON {table}")
        op.execute("DROP FUNCTION reject_research_mutation()")
