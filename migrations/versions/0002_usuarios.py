"""Cria a tabela de usuários."""

from alembic import op
import sqlalchemy as sa

revision = "0002_usuarios"
down_revision = "0001_esqueleto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("apelido", sa.String(length=12), nullable=False),
        sa.Column("senha_hash", sa.Text(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("falhas_login", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_usuarios"),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )
    op.create_index(
        "uq_usuarios_apelido_lower",
        "usuarios",
        [sa.text("lower(apelido)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_usuarios_apelido_lower", table_name="usuarios")
    op.drop_table("usuarios")
