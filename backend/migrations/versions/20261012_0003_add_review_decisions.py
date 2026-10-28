"""Add immutable administrative review decisions."""

from alembic import op
import sqlalchemy as sa


revision = "20261012_0003"
down_revision = "20261012_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("verification_run_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("previous_status", sa.String(), nullable=False),
        sa.Column("resulting_status", sa.String(), nullable=False),
        sa.Column("assessment_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["verification_run_id"],
            ["verification_runs.id"]
        ),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(
        "ix_review_decisions_id",
        "review_decisions",
        ["id"]
    )
    op.create_index(
        "ix_review_decisions_claim_id",
        "review_decisions",
        ["claim_id"]
    )


def downgrade():
    op.drop_index(
        "ix_review_decisions_claim_id",
        table_name="review_decisions"
    )
    op.drop_index(
        "ix_review_decisions_id",
        table_name="review_decisions"
    )
    op.drop_table("review_decisions")
