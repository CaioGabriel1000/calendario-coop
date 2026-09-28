"""Adiciona marcações de disponibilidade."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_marcacoes"
down_revision = "0003_sessoes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "disponivel", "indisponivel", name="status_marcacao", create_type=False
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "marcacoes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_marcacoes_usuario_id_usuarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_marcacoes"),
        sa.UniqueConstraint("usuario_id", "data", name="uq_marcacoes_usuario_data"),
    )
    op.create_index("ix_marcacoes_data", "marcacoes", ["data"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_marcacoes_data", table_name="marcacoes")
    op.drop_table("marcacoes")
    postgresql.ENUM(name="status_marcacao").drop(op.get_bind(), checkfirst=True)
