"""Comandos administrativos do Calendário Coop."""

from typing import Annotated

import typer

from app.db import SessionLocal
from app.usuarios import criar_usuario, listar_usuarios

app = typer.Typer(no_args_is_help=True, help="Administração do Calendário Coop.")


@app.command("create-user")
def create_user(
    email: Annotated[str, typer.Option("--email", help="E-mail de acesso.")],
    nome: Annotated[str, typer.Option("--nome", help="Nome completo.")],
    apelido: Annotated[str, typer.Option("--apelido", help="Apelido com até 12 caracteres.")],
    senha: Annotated[
        str | None,
        typer.Option("--senha", help="Senha (evite usar no shell)."),
    ] = None,
) -> None:
    if senha is None:
        senha = typer.prompt("Senha", hide_input=True)
        confirmacao = typer.prompt("Confirme a senha", hide_input=True)
        if senha != confirmacao:
            typer.echo("Erro: as senhas não conferem.", err=True)
            raise typer.Exit(code=1)

    db = SessionLocal()
    try:
        usuario = criar_usuario(
            db,
            email=email,
            nome=nome,
            apelido=apelido,
            senha=senha,
        )
    except ValueError as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo("Erro: não foi possível criar o usuário.", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        db.close()

    typer.echo(f"Usuário {usuario.email} criado com sucesso.")


@app.command("list-users")
def list_users(
    todos: Annotated[
        bool,
        typer.Option("--todos", help="Inclui usuários desativados."),
    ] = False,
) -> None:
    db = SessionLocal()
    try:
        usuarios = listar_usuarios(db, incluir_desativados=todos)
    except Exception as exc:
        typer.echo("Erro: não foi possível listar os usuários.", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        db.close()

    if not usuarios:
        typer.echo("Nenhum usuário encontrado.")
        return

    typer.echo("E-mail | Nome | Apelido | Status | Criado em")
    for usuario in usuarios:
        status = "ativo" if usuario.ativo else "desativado"
        criado_em = usuario.criado_em.strftime("%d/%m/%Y %H:%M")
        typer.echo(
            f"{usuario.email} | {usuario.nome} | {usuario.apelido} | "
            f"{status} | {criado_em}"
        )
