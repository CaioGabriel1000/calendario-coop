"""Adiciona telefone obrigatório aos usuários."""

from alembic import op
import sqlalchemy as sa


revision = "0005_telefone_usuarios"
down_revision = "0004_marcacoes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    usuarios_existentes = bind.execute(
        sa.text("SELECT count(*) FROM usuarios")
    ).scalar_one()
    if usuarios_existentes:
        raise RuntimeError(
            "A migration de telefone exige que os usuários existentes recebam "
            "números reais antes da aplicação. Nenhuma linha foi alterada."
        )

    op.add_column(
        "usuarios",
        sa.Column("telefone", sa.CHAR(length=11), nullable=False),
    )
    op.create_check_constraint(
        "ck_usuarios_telefone_formato",
        "usuarios",
        "telefone ~ '^[0-9]{11}$'",
    )
    op.create_unique_constraint(
        "uq_usuarios_telefone", "usuarios", ["telefone"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_usuarios_telefone", "usuarios", type_="unique")
    op.drop_constraint("ck_usuarios_telefone_formato", "usuarios", type_="check")
    op.drop_column("usuarios", "telefone")
