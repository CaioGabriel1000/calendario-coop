"""Rotas de login e logout."""

import secrets
from datetime import timedelta
from math import ceil

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    COOKIE_CSRF_PRE_SESSAO,
    COOKIE_SESSAO,
    SessaoAutenticada,
    criar_sessao,
    localizar_sessao,
    remover_sessoes_expiradas,
    requer_csrf,
)
from app.config import get_settings
from app.db import get_db
from app.models import Usuario
from app.relogio import agora_utc
from app.senhas import verificar_senha

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
ERRO_CREDENCIAIS = "E-mail ou senha inválidos."
IDADE_COOKIE_PRE_SESSAO = 600


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    autenticacao = localizar_sessao(db, request.cookies.get(COOKIE_SESSAO))
    if autenticacao is not None:
        return RedirectResponse(url="/", status_code=303)

    csrf_token = secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"csrf_token": csrf_token, "erro": None},
    )
    response.set_cookie(
        COOKIE_CSRF_PRE_SESSAO,
        csrf_token,
        max_age=IDADE_COOKIE_PRE_SESSAO,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/login",
    )
    return response


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    csrf_cookie = request.cookies.get(COOKIE_CSRF_PRE_SESSAO)
    if not csrf_cookie or not secrets.compare_digest(csrf_cookie, csrf_token):
        raise HTTPException(status_code=403, detail="Token CSRF inválido.")

    remover_sessoes_expiradas(db)
    usuario = db.scalar(
        select(Usuario)
        .where(Usuario.email == email.strip().lower())
        .with_for_update()
    )
    if usuario is None or not usuario.ativo:
        response = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"csrf_token": csrf_cookie, "erro": ERRO_CREDENCIAIS},
        )
        response.status_code = 200
        return response

    agora = agora_utc()
    if usuario.bloqueado_ate is not None and usuario.bloqueado_ate > agora:
        minutos = max(1, ceil((usuario.bloqueado_ate - agora).total_seconds() / 60))
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "csrf_token": csrf_cookie,
                "erro": f"Muitas tentativas. Tente novamente em {minutos} minutos.",
            },
        )

    if usuario.bloqueado_ate is not None:
        usuario.falhas_login = 0
        usuario.bloqueado_ate = None

    if not verificar_senha(usuario.senha_hash, senha):
        usuario.falhas_login += 1
        if usuario.falhas_login >= get_settings().login_max_falhas:
            usuario.bloqueado_ate = agora + timedelta(
                minutes=get_settings().login_bloqueio_minutos
            )
            db.commit()
            minutos = get_settings().login_bloqueio_minutos
            mensagem = f"Muitas tentativas. Tente novamente em {minutos} minutos."
        else:
            db.commit()
            mensagem = ERRO_CREDENCIAIS
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"csrf_token": csrf_cookie, "erro": mensagem},
        )

    usuario.falhas_login = 0
    usuario.bloqueado_ate = None
    db.commit()
    _, token = criar_sessao(db, usuario)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        COOKIE_SESSAO,
        token,
        max_age=get_settings().sessao_dias * 24 * 60 * 60,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(COOKIE_CSRF_PRE_SESSAO, path="/login")
    return response


@router.post("/logout")
def logout(
    autenticacao: SessaoAutenticada = Depends(requer_csrf),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    db.delete(autenticacao.sessao)
    db.commit()
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_SESSAO, path="/")
    return response
