"""Create the initial TrustLens schema."""

from alembic import op
import sqlalchemy as sa


revision = "20261012_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_number", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True
        ),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_claims_id", "claims", ["id"])
    op.create_index(
        "ix_claims_claim_number",
        "claims",
        ["claim_number"],
        unique=True
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("stored_filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_evidence_id", "evidence", ["id"])

    op.create_table(
        "verification_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("pipeline_version", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(
        "ix_verification_runs_id",
        "verification_runs",
        ["id"]
    )

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("verification_run_id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=True),
        sa.Column("analysis_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
        sa.ForeignKeyConstraint(
            ["verification_run_id"],
            ["verification_runs.id"]
        ),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index(
        "ix_analysis_results_id",
        "analysis_results",
        ["id"]
    )


def downgrade():
    op.drop_index("ix_analysis_results_id", table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index("ix_verification_runs_id", table_name="verification_runs")
    op.drop_table("verification_runs")
    op.drop_index("ix_evidence_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_claims_claim_number", table_name="claims")
    op.drop_index("ix_claims_id", table_name="claims")
    op.drop_table("claims")
