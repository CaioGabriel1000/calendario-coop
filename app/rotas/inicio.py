"""Página inicial temporária após o login."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import SessaoAutenticada, requer_sessao

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def inicio(
    request: Request,
    autenticacao: SessaoAutenticada = Depends(requer_sessao),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="inicio.html",
        context={
            "apelido": autenticacao.usuario.apelido,
            "csrf_token": autenticacao.sessao.csrf_token,
        },
    )
