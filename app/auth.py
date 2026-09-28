"""Sessões, autenticação e proteção CSRF."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Sessao, Usuario

COOKIE_SESSAO = "sessao"
COOKIE_CSRF_PRE_SESSAO = "csrf_pre_sessao"


@dataclass(frozen=True, slots=True)
class SessaoAutenticada:
    usuario: Usuario
    sessao: Sessao


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_sessao(db: Session, usuario: Usuario) -> tuple[Sessao, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    agora = datetime.now(timezone.utc)
    sessao = Sessao(
        usuario_id=usuario.id,
        token_hash=hash_token(token),
        csrf_token=csrf_token,
        expira_em=agora + timedelta(days=get_settings().sessao_dias),
    )
    db.add(sessao)
    db.commit()
    db.refresh(sessao)
    return sessao, token


def localizar_sessao(db: Session, token: str | None) -> SessaoAutenticada | None:
    if not token:
        return None
    agora = datetime.now(timezone.utc)
    resultado = db.execute(
        select(Sessao, Usuario)
        .join(Usuario, Usuario.id == Sessao.usuario_id)
        .where(
            Sessao.token_hash == hash_token(token),
            Sessao.expira_em > agora,
            Usuario.ativo.is_(True),
        )
    ).first()
    if resultado is None:
        return None
    sessao, usuario = resultado
    return SessaoAutenticada(usuario=usuario, sessao=sessao)


def requer_sessao(
    request: Request,
    db: Session = Depends(get_db),
) -> SessaoAutenticada:
    autenticacao = localizar_sessao(db, request.cookies.get(COOKIE_SESSAO))
    if autenticacao is not None:
        return autenticacao
    if request.headers.get("HX-Request", "").lower() == "true":
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária.",
            headers={"HX-Redirect": "/login"},
        )
    raise HTTPException(
        status_code=303,
        headers={"Location": "/login"},
    )


async def requer_csrf(
    request: Request,
    autenticacao: SessaoAutenticada = Depends(requer_sessao),
) -> SessaoAutenticada:
    csrf_enviado = request.headers.get("X-CSRF-Token")
    if not csrf_enviado:
        formulario = await request.form()
        valor = formulario.get("csrf_token")
        csrf_enviado = valor if isinstance(valor, str) else None
    if not csrf_enviado or not secrets.compare_digest(
        csrf_enviado, autenticacao.sessao.csrf_token
    ):
        raise HTTPException(status_code=403, detail="Token CSRF inválido.")
    return autenticacao


def remover_sessoes_expiradas(db: Session) -> None:
    db.execute(delete(Sessao).where(Sessao.expira_em <= datetime.now(timezone.utc)))
    db.commit()
