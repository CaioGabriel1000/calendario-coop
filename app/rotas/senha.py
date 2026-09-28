"""Tela e operação de alteração da própria senha."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import SessaoAutenticada, requer_csrf, requer_sessao
from app.db import get_db
from app.usuarios import ErroAlteracaoSenha, alterar_senha_usuario

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def renderizar_pagina(
    request: Request,
    autenticacao: SessaoAutenticada,
    *,
    erro: str | None = None,
    sucesso: bool = False,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="senha.html",
        context={
            "csrf_token": autenticacao.sessao.csrf_token,
            "apelido": autenticacao.usuario.apelido,
            "erro": erro,
            "sucesso": sucesso,
        },
    )


@router.get("/senha", response_class=HTMLResponse)
def pagina_senha(
    request: Request,
    autenticacao: SessaoAutenticada = Depends(requer_sessao),
) -> Response:
    return renderizar_pagina(request, autenticacao)


@router.post("/senha", response_class=HTMLResponse)
def alterar_senha(
    request: Request,
    senha_atual: str = Form(...),
    nova_senha: str = Form(...),
    confirmar_senha: str = Form(...),
    autenticacao: SessaoAutenticada = Depends(requer_csrf),
    db: Session = Depends(get_db),
) -> Response:
    try:
        alterar_senha_usuario(
            db,
            usuario_id=autenticacao.usuario.id,
            sessao_atual_id=autenticacao.sessao.id,
            senha_atual=senha_atual,
            nova_senha=nova_senha,
            confirmacao=confirmar_senha,
        )
    except ErroAlteracaoSenha as exc:
        return renderizar_pagina(request, autenticacao, erro=str(exc))
    return renderizar_pagina(request, autenticacao, sucesso=True)
