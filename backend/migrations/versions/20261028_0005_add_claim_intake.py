"""Add structured claim intake and draft timestamps."""

from alembic import op
import sqlalchemy as sa


revision = "20261028_0005"
down_revision = "20261026_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("claims") as batch_op:
        batch_op.add_column(sa.Column("claim_type", sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column("item_name", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("reference_number", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("incident_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("incident_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("intake_version", sa.Integer(), server_default="1", nullable=False))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("claims") as batch_op:
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("intake_version")
        batch_op.drop_column("incident_summary")
        batch_op.drop_column("incident_date")
        batch_op.drop_column("reference_number")
        batch_op.drop_column("item_name")
        batch_op.drop_column("claim_type")
