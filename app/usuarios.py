"""Operações de cadastro e consulta de usuários."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Usuario
from app.senhas import gerar_hash

TAMANHO_MINIMO_SENHA = 8
TAMANHO_MAXIMO_APELIDO = 12


class UsuarioDuplicadoError(ValueError):
    """Indica que e-mail ou apelido já está cadastrado."""


def criar_usuario(
    db: Session,
    *,
    email: str,
    nome: str,
    apelido: str,
    senha: str,
) -> Usuario:
    email_normalizado = email.strip().lower()
    nome_normalizado = nome.strip()
    apelido_normalizado = apelido.strip()

    if not email_normalizado:
        raise ValueError("O e-mail é obrigatório.")
    if not nome_normalizado:
        raise ValueError("O nome é obrigatório.")
    if not apelido_normalizado:
        raise ValueError("O apelido é obrigatório.")
    if len(apelido_normalizado) > TAMANHO_MAXIMO_APELIDO:
        raise ValueError("O apelido deve ter no máximo 12 caracteres.")
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ValueError("A senha deve ter no mínimo 8 caracteres.")

    if db.scalar(select(Usuario.id).where(Usuario.email == email_normalizado)):
        raise UsuarioDuplicadoError("Este e-mail já está cadastrado.")
    if db.scalar(
        select(Usuario.id).where(func.lower(Usuario.apelido) == apelido_normalizado.lower())
    ):
        raise UsuarioDuplicadoError("Este apelido já está cadastrado.")

    usuario = Usuario(
        email=email_normalizado,
        nome=nome_normalizado,
        apelido=apelido_normalizado,
        senha_hash=gerar_hash(senha),
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_usuarios_email":
            raise UsuarioDuplicadoError("Este e-mail já está cadastrado.") from exc
        if constraint == "uq_usuarios_apelido_lower":
            raise UsuarioDuplicadoError("Este apelido já está cadastrado.") from exc
        raise UsuarioDuplicadoError("E-mail ou apelido já cadastrado.") from exc

    db.refresh(usuario)
    return usuario


def listar_usuarios(db: Session, *, incluir_desativados: bool = False) -> list[Usuario]:
    consulta = select(Usuario)
    if not incluir_desativados:
        consulta = consulta.where(Usuario.ativo.is_(True))
    consulta = consulta.order_by(func.lower(Usuario.apelido), Usuario.id)
    return list(db.scalars(consulta).all())
