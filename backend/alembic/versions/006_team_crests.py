"""Retain the fixture provider's explicit club crest URL."""

import sqlalchemy as sa
from alembic import op

revision = "006_crests"
down_revision = "005_picks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("teams", sa.Column("crest_url", sa.String(300), nullable=True))


def downgrade():
    op.drop_column("teams", "crest_url")
