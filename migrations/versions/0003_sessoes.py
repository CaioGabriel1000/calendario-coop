"""Cria a tabela de sessões."""

from alembic import op
import sqlalchemy as sa

revision = "0003_sessoes"
down_revision = "0002_usuarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessoes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("csrf_token", sa.Text(), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_sessoes_usuario_id_usuarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sessoes"),
        sa.UniqueConstraint("token_hash", name="uq_sessoes_token_hash"),
    )


def downgrade() -> None:
    op.drop_table("sessoes")
