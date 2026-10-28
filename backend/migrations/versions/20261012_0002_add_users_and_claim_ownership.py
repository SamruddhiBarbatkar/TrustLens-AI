"""Add user accounts and claim ownership."""

from alembic import op
import sqlalchemy as sa


revision = "20261012_0002"
down_revision = "20261012_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True
        ),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    with op.batch_alter_table("claims") as batch_op:
        batch_op.add_column(
            sa.Column("owner_id", sa.Integer(), nullable=True)
        )
        batch_op.create_index("ix_claims_owner_id", ["owner_id"])
        batch_op.create_foreign_key(
            "fk_claims_owner_id_users",
            "users",
            ["owner_id"],
            ["id"]
        )


def downgrade():
    with op.batch_alter_table("claims") as batch_op:
        batch_op.drop_constraint(
            "fk_claims_owner_id_users",
            type_="foreignkey"
        )
        batch_op.drop_index("ix_claims_owner_id")
        batch_op.drop_column("owner_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
