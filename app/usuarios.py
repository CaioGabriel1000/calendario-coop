"""Operações de cadastro e consulta de usuários."""

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Marcacao, Sessao, Usuario
from app.senhas import gerar_hash, verificar_senha
from app.telefones import normalizar_telefone

TAMANHO_MINIMO_SENHA = 8
TAMANHO_MAXIMO_APELIDO = 12


class ErroAlteracaoSenha(ValueError):
    """Indica uma validação que impediu a troca da senha."""


class UsuarioDuplicadoError(ValueError):
    """Indica que e-mail, telefone ou apelido já está cadastrado."""


class UsuarioNaoEncontradoError(ValueError):
    """Indica que não existe usuário com o e-mail informado."""


def criar_usuario(
    db: Session,
    *,
    email: str,
    telefone: str,
    nome: str,
    apelido: str,
    senha: str,
) -> Usuario:
    email_normalizado = email.strip().lower()
    telefone_normalizado = normalizar_telefone(telefone)
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
    if db.scalar(select(Usuario.id).where(Usuario.telefone == telefone_normalizado)):
        raise UsuarioDuplicadoError("Este telefone já está cadastrado.")
    if db.scalar(
        select(Usuario.id).where(func.lower(Usuario.apelido) == apelido_normalizado.lower())
    ):
        raise UsuarioDuplicadoError("Este apelido já está cadastrado.")

    usuario = Usuario(
        email=email_normalizado,
        telefone=telefone_normalizado,
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
        if constraint == "uq_usuarios_telefone":
            raise UsuarioDuplicadoError("Este telefone já está cadastrado.") from exc
        if constraint == "uq_usuarios_apelido_lower":
            raise UsuarioDuplicadoError("Este apelido já está cadastrado.") from exc
        raise UsuarioDuplicadoError("E-mail, telefone ou apelido já cadastrado.") from exc

    db.refresh(usuario)
    return usuario


def listar_usuarios(db: Session, *, incluir_desativados: bool = False) -> list[Usuario]:
    consulta = select(Usuario)
    if not incluir_desativados:
        consulta = consulta.where(Usuario.ativo.is_(True))
    consulta = consulta.order_by(func.lower(Usuario.apelido), Usuario.id)
    return list(db.scalars(consulta).all())


def alterar_senha_usuario(
    db: Session,
    *,
    usuario_id: int,
    sessao_atual_id: int,
    senha_atual: str,
    nova_senha: str,
    confirmacao: str,
) -> None:
    usuario = db.scalar(
        select(Usuario).where(Usuario.id == usuario_id).with_for_update()
    )
    if usuario is None or not verificar_senha(usuario.senha_hash, senha_atual):
        raise ErroAlteracaoSenha("A senha atual está incorreta.")
    if len(nova_senha) < TAMANHO_MINIMO_SENHA:
        raise ErroAlteracaoSenha("A nova senha deve ter no mínimo 8 caracteres.")
    if nova_senha != confirmacao:
        raise ErroAlteracaoSenha("A confirmação da nova senha não confere.")

    usuario.senha_hash = gerar_hash(nova_senha)
    usuario.atualizado_em = func.now()
    db.execute(
        delete(Sessao).where(
            Sessao.usuario_id == usuario_id,
            Sessao.id != sessao_atual_id,
        )
    )
    db.commit()


def resetar_senha_usuario(db: Session, *, email: str, senha: str) -> Usuario:
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ValueError("A senha deve ter no mínimo 8 caracteres.")
    usuario = db.scalar(
        select(Usuario)
        .where(Usuario.email == email.strip().lower())
        .with_for_update()
    )
    if usuario is None:
        raise UsuarioNaoEncontradoError("Usuário não encontrado.")

    usuario.senha_hash = gerar_hash(senha)
    usuario.falhas_login = 0
    usuario.bloqueado_ate = None
    usuario.atualizado_em = func.now()
    db.execute(delete(Sessao).where(Sessao.usuario_id == usuario.id))
    db.commit()
    db.refresh(usuario)
    return usuario


def atualizar_usuario(
    db: Session,
    *,
    email: str,
    novo_email: str | None = None,
    novo_telefone: str | None = None,
    nome: str | None = None,
    apelido: str | None = None,
) -> Usuario:
    if novo_email is None and novo_telefone is None and nome is None and apelido is None:
        raise ValueError("Informe ao menos um campo para atualizar.")

    email_atual = email.strip().lower()
    usuario = db.scalar(
        select(Usuario).where(Usuario.email == email_atual).with_for_update()
    )
    if usuario is None:
        raise UsuarioNaoEncontradoError("Usuário não encontrado.")

    email_atualizado = novo_email.strip().lower() if novo_email is not None else None
    telefone_atualizado = (
        normalizar_telefone(novo_telefone) if novo_telefone is not None else None
    )
    nome_atualizado = nome.strip() if nome is not None else None
    apelido_atualizado = apelido.strip() if apelido is not None else None

    if email_atualizado is not None and not email_atualizado:
        raise ValueError("O novo e-mail não pode ficar vazio.")
    if nome_atualizado is not None and not nome_atualizado:
        raise ValueError("O nome não pode ficar vazio.")
    if apelido_atualizado is not None:
        if not apelido_atualizado:
            raise ValueError("O apelido não pode ficar vazio.")
        if len(apelido_atualizado) > TAMANHO_MAXIMO_APELIDO:
            raise ValueError("O apelido deve ter no máximo 12 caracteres.")

    if email_atualizado is not None and db.scalar(
        select(Usuario.id).where(
            Usuario.email == email_atualizado,
            Usuario.id != usuario.id,
        )
    ):
        raise UsuarioDuplicadoError("Este e-mail já está cadastrado.")
    if telefone_atualizado is not None and db.scalar(
        select(Usuario.id).where(
            Usuario.telefone == telefone_atualizado,
            Usuario.id != usuario.id,
        )
    ):
        raise UsuarioDuplicadoError("Este telefone já está cadastrado.")
    if apelido_atualizado is not None and db.scalar(
        select(Usuario.id).where(
            func.lower(Usuario.apelido) == apelido_atualizado.lower(),
            Usuario.id != usuario.id,
        )
    ):
        raise UsuarioDuplicadoError("Este apelido já está cadastrado.")

    if email_atualizado is not None:
        usuario.email = email_atualizado
    if telefone_atualizado is not None:
        usuario.telefone = telefone_atualizado
    if nome_atualizado is not None:
        usuario.nome = nome_atualizado
    if apelido_atualizado is not None:
        usuario.apelido = apelido_atualizado
    usuario.atualizado_em = func.now()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_usuarios_email":
            raise UsuarioDuplicadoError("Este e-mail já está cadastrado.") from exc
        if constraint == "uq_usuarios_telefone":
            raise UsuarioDuplicadoError("Este telefone já está cadastrado.") from exc
        if constraint == "uq_usuarios_apelido_lower":
            raise UsuarioDuplicadoError("Este apelido já está cadastrado.") from exc
        raise UsuarioDuplicadoError("E-mail, telefone ou apelido já cadastrado.") from exc
    db.refresh(usuario)
    return usuario


def desativar_usuario(db: Session, *, email: str, data_hoje: date) -> Usuario:
    usuario = db.scalar(
        select(Usuario)
        .where(Usuario.email == email.strip().lower())
        .with_for_update()
    )
    if usuario is None:
        raise UsuarioNaoEncontradoError("Usuário não encontrado.")

    usuario.ativo = False
    usuario.atualizado_em = func.now()
    db.execute(
        delete(Marcacao).where(
            Marcacao.usuario_id == usuario.id,
            Marcacao.data >= data_hoje,
        )
    )
    db.execute(delete(Sessao).where(Sessao.usuario_id == usuario.id))
    db.commit()
    db.refresh(usuario)
    return usuario


def reativar_usuario(db: Session, *, email: str) -> Usuario:
    usuario = db.scalar(
        select(Usuario)
        .where(Usuario.email == email.strip().lower())
        .with_for_update()
    )
    if usuario is None:
        raise UsuarioNaoEncontradoError("Usuário não encontrado.")
    usuario.ativo = True
    usuario.atualizado_em = func.now()
    db.commit()
    db.refresh(usuario)
    return usuario
