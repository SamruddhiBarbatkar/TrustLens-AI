"""Add claimant-supplied and technical context to evidence."""

from alembic import op
import sqlalchemy as sa


revision = "20261026_0004"
down_revision = "20261012_0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("evidence") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source_type", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("location_label", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("image_width", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("image_height", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("evidence") as batch_op:
        batch_op.drop_column("image_height")
        batch_op.drop_column("image_width")
        batch_op.drop_column("file_size_bytes")
        batch_op.drop_column("location_label")
        batch_op.drop_column("captured_at")
        batch_op.drop_column("source_type")
        batch_op.drop_column("description")
