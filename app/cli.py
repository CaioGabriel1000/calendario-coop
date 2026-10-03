"""Comandos administrativos do Calendário Coop."""

from typing import Annotated

import typer

from app.db import SessionLocal
from app.relogio import hoje
from app.usuarios import (
    atualizar_usuario,
    criar_usuario,
    desativar_usuario,
    listar_usuarios,
    reativar_usuario,
    resetar_senha_usuario,
)

app = typer.Typer(no_args_is_help=True, help="Administração do Calendário Coop.")


def obter_senha(senha: str | None) -> str:
    if senha is not None:
        return senha
    senha = typer.prompt("Senha", hide_input=True)
    confirmacao = typer.prompt("Confirme a senha", hide_input=True)
    if senha != confirmacao:
        typer.echo("Erro: as senhas não conferem.", err=True)
        raise typer.Exit(code=1)
    return senha


@app.command("create-user")
def create_user(
    email: Annotated[str, typer.Option("--email", help="E-mail de acesso.")],
    telefone: Annotated[str, typer.Option("--telefone", help="Telefone com DDD.")],
    nome: Annotated[str, typer.Option("--nome", help="Nome completo.")],
    apelido: Annotated[str, typer.Option("--apelido", help="Apelido com até 12 caracteres.")],
    senha: Annotated[
        str | None,
        typer.Option("--senha", help="Senha (evite usar no shell)."),
    ] = None,
) -> None:
    senha = obter_senha(senha)

    db = SessionLocal()
    try:
        usuario = criar_usuario(
            db,
            email=email,
            telefone=telefone,
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


@app.command("reset-password")
def reset_password(
    email: Annotated[str, typer.Option("--email", help="E-mail da conta.")],
    senha: Annotated[
        str | None,
        typer.Option("--senha", help="Nova senha (evite usar no shell)."),
    ] = None,
) -> None:
    senha = obter_senha(senha)
    db = SessionLocal()
    try:
        usuario = resetar_senha_usuario(db, email=email, senha=senha)
    except ValueError as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo("Erro: não foi possível redefinir a senha.", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        db.close()
    typer.echo(f"Senha do usuário {usuario.email} redefinida; sessões encerradas.")


@app.command("update-user")
def update_user(
    email: Annotated[str, typer.Option("--email", help="E-mail atual da conta.")],
    novo_email: Annotated[
        str | None,
        typer.Option("--novo-email", help="Novo e-mail de acesso."),
    ] = None,
    novo_telefone: Annotated[
        str | None,
        typer.Option("--novo-telefone", help="Novo telefone com DDD."),
    ] = None,
    nome: Annotated[str | None, typer.Option("--nome", help="Novo nome.")] = None,
    apelido: Annotated[
        str | None,
        typer.Option("--apelido", help="Novo apelido com até 12 caracteres."),
    ] = None,
) -> None:
    db = SessionLocal()
    try:
        usuario = atualizar_usuario(
            db,
            email=email,
            novo_email=novo_email,
            novo_telefone=novo_telefone,
            nome=nome,
            apelido=apelido,
        )
    except ValueError as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo("Erro: não foi possível atualizar o usuário.", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        db.close()
    typer.echo(f"Usuário {usuario.email} atualizado com sucesso.")


@app.command("deactivate-user")
def deactivate_user(
    email: Annotated[str, typer.Option("--email", help="E-mail da conta.")],
) -> None:
    if not typer.confirm(f"Confirma a desativação de {email}?"):
        typer.echo("Operação cancelada.")
        return

    db = SessionLocal()
    try:
        usuario = desativar_usuario(db, email=email, data_hoje=hoje())
    except ValueError as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo("Erro: não foi possível desativar o usuário.", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        db.close()
    typer.echo(f"Usuário {usuario.email} desativado; sessões encerradas.")


@app.command("reactivate-user")
def reactivate_user(
    email: Annotated[str, typer.Option("--email", help="E-mail da conta.")],
) -> None:
    db = SessionLocal()
    try:
        usuario = reativar_usuario(db, email=email)
    except ValueError as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo("Erro: não foi possível reativar o usuário.", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        db.close()
    typer.echo(f"Usuário {usuario.email} reativado com sucesso.")


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
