from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.auth import hash_token
from app.cli import app as cli_app
from app.main import app as web_app
from app.models import Marcacao, Sessao, StatusMarcacao, Usuario
from app.senhas import verificar_senha
from app.usuarios import UsuarioDuplicadoError, criar_usuario
from apoio import telefone_de_teste

runner = CliRunner()


def configurar_cli(monkeypatch, db_session):
    def criar_sessao():
        return Session(
            bind=db_session.connection(),
            join_transaction_mode="create_savepoint",
        )

    monkeypatch.setattr("app.cli.SessionLocal", criar_sessao)


def criar(
    db_session,
    *,
    email="ana@example.com",
    telefone=None,
    nome="Ana Souza",
    apelido="Ana",
    senha="senha-segura",
):
    return criar_usuario(
        db_session,
        email=email,
        telefone=telefone or telefone_de_teste(email),
        nome=nome,
        apelido=apelido,
        senha=senha,
    )


def test_email_unico_sem_diferenciar_maiusculas(db_session):
    usuario = criar(db_session)

    assert usuario.email == "ana@example.com"
    with pytest.raises(UsuarioDuplicadoError, match="e-mail"):
        criar(db_session, email="ANA@EXAMPLE.COM", apelido="Outra")


def test_cadastro_normaliza_telefone_antes_de_salvar(db_session):
    usuario = criar(db_session, telefone="(31) 99999-9999")

    assert usuario.telefone == "31999999999"


def test_cadastro_rejeita_telefone_invalido(db_session):
    with pytest.raises(ValueError, match="telefone"):
        criar(db_session, telefone="31 9999-9999")

    assert db_session.query(Usuario).count() == 0


def test_create_user_cli_persiste_telefone_normalizado(db_session, monkeypatch):
    configurar_cli(monkeypatch, db_session)

    resultado = runner.invoke(
        cli_app,
        [
            "create-user",
            "--email",
            "telefone@example.com",
            "--telefone",
            "(31) 99999-9999",
            "--nome",
            "Pessoa Teste",
            "--apelido",
            "Telefone",
            "--senha",
            "senha-segura",
        ],
    )

    assert resultado.exit_code == 0
    usuario = db_session.scalar(
        select(Usuario).where(Usuario.email == "telefone@example.com")
    )
    assert usuario is not None
    assert usuario.telefone == "31999999999"


def test_create_user_cli_exige_telefone():
    resultado = runner.invoke(
        cli_app,
        [
            "create-user",
            "--email",
            "sem-telefone@example.com",
            "--nome",
            "Pessoa Teste",
            "--apelido",
            "SemTelefone",
            "--senha",
            "senha-segura",
        ],
    )

    assert resultado.exit_code != 0
    assert "--telefone" in resultado.output


def test_create_user_cli_rejeita_telefone_invalido_e_duplicado(
    db_session, monkeypatch
):
    configurar_cli(monkeypatch, db_session)
    existente = criar(db_session)

    argumentos_base = [
        "create-user",
        "--email",
        "novo@example.com",
        "--nome",
        "Pessoa Teste",
        "--apelido",
        "Novo",
        "--senha",
        "senha-segura",
    ]
    invalido = runner.invoke(
        cli_app,
        [*argumentos_base, "--telefone", "31 9999-9999"],
    )
    duplicado = runner.invoke(
        cli_app,
        [*argumentos_base, "--telefone", existente.telefone],
    )

    assert invalido.exit_code == 1
    assert "Erro:" in invalido.output
    assert "telefone" in invalido.output.lower()
    assert duplicado.exit_code == 1
    assert "Este telefone já está cadastrado." in duplicado.output


@pytest.mark.parametrize(
    "argumentos",
    [
        ["reset-password", "--email", "ana@example.com", "--telefone", "31999999999", "--senha", "senha-segura"],
        ["update-user", "--apelido", "Novo"],
        ["deactivate-user"],
        ["reactivate-user", "--email", "ana@example.com", "--telefone", "31999999999"],
    ],
)
def test_comandos_de_manutencao_exigem_um_identificador(argumentos):
    resultado = runner.invoke(cli_app, argumentos)

    assert resultado.exit_code == 1
    assert "informe exatamente um identificador" in resultado.output.lower()


def test_list_users_exibe_telefone(db_session, monkeypatch):
    configurar_cli(monkeypatch, db_session)
    usuario = criar(db_session, telefone="(31) 99999-9999")

    resultado = runner.invoke(cli_app, ["list-users"])

    assert resultado.exit_code == 0
    assert "E-mail | Telefone" in resultado.output
    assert f"{usuario.email} | 31999999999 |" in resultado.output


def test_apelido_unico_sem_diferenciar_maiusculas_incluindo_desativado(db_session):
    usuario = criar(db_session)
    usuario.ativo = False
    db_session.flush()

    with pytest.raises(UsuarioDuplicadoError, match="apelido"):
        criar(db_session, email="outra@example.com", apelido="aNA")


def test_telefone_unico_incluindo_usuario_desativado(db_session):
    usuario = criar(db_session, telefone="(31) 99999-9999")
    usuario.ativo = False
    db_session.flush()

    with pytest.raises(UsuarioDuplicadoError, match="telefone"):
        criar(
            db_session,
            email="outra@example.com",
            telefone="31999999999",
            apelido="Outra",
        )


def test_senha_com_menos_de_oito_caracteres_e_recusada(db_session):
    with pytest.raises(ValueError, match="no mínimo 8"):
        criar(db_session, senha="curta")

    assert db_session.query(Usuario).count() == 0


def test_reset_password_limpa_bloqueio_e_encerra_sessoes(
    db_session, monkeypatch
):
    configurar_cli(monkeypatch, db_session)
    usuario = criar(db_session)
    usuario.falhas_login = 5
    usuario.bloqueado_ate = datetime.now(timezone.utc) + timedelta(minutes=10)
    db_session.flush()
    for indice in range(2):
        token = f"reset-sessao-{indice}"
        db_session.add(
            Sessao(
                usuario_id=usuario.id,
                token_hash=hash_token(token),
                csrf_token=f"csrf-{token}",
                expira_em=datetime.now(timezone.utc) + timedelta(days=1),
            )
        )
    db_session.flush()

    resultado = runner.invoke(
        cli_app,
        [
            "reset-password",
            "--telefone",
            usuario.telefone,
            "--senha",
            "senha-redefinida",
        ],
    )

    assert resultado.exit_code == 0
    assert "sessões encerradas" in resultado.output
    db_session.expire_all()
    usuario = db_session.scalar(
        select(Usuario).where(Usuario.email == "ana@example.com")
    )
    assert usuario is not None
    assert verificar_senha(usuario.senha_hash, "senha-redefinida")
    assert usuario.falhas_login == 0
    assert usuario.bloqueado_ate is None
    assert db_session.scalar(
        select(Sessao.id).where(Sessao.usuario_id == usuario.id)
    ) is None


def test_update_user_normaliza_e_respeita_unicidade(db_session, monkeypatch):
    configurar_cli(monkeypatch, db_session)
    alvo = criar(db_session)
    bia = criar(
        db_session,
        email="bia@example.com",
        nome="Bia",
        apelido="Bia",
    )

    atualizado = runner.invoke(
        cli_app,
        [
            "update-user",
            "--email",
            alvo.email,
            "--novo-telefone",
            "(31) 99999-9999",
            "--novo-email",
            " ANA.NOVA@EXAMPLE.COM ",
            "--nome",
            "Ana Atualizada",
            "--apelido",
            "Aninha",
        ],
    )
    email_duplicado = runner.invoke(
        cli_app,
        [
            "update-user",
            "--email",
            "ana.nova@example.com",
            "--novo-email",
            "BIA@example.com",
        ],
    )
    apelido_duplicado = runner.invoke(
        cli_app,
        [
            "update-user",
            "--email",
            "ana.nova@example.com",
            "--apelido",
            "bIA",
        ],
    )
    telefone_duplicado = runner.invoke(
        cli_app,
        [
            "update-user",
            "--email",
            "ana.nova@example.com",
            "--novo-telefone",
            bia.telefone,
        ],
    )
    email_vazio = runner.invoke(
        cli_app,
        [
            "update-user",
            "--email",
            "ana.nova@example.com",
            "--novo-email",
            " ",
        ],
    )
    telefone_vazio = runner.invoke(
        cli_app,
        [
            "update-user",
            "--email",
            "ana.nova@example.com",
            "--novo-telefone",
            "",
        ],
    )

    assert atualizado.exit_code == 0
    assert "ana.nova@example.com" in atualizado.output
    assert email_duplicado.exit_code == 1
    assert "Este e-mail já está cadastrado." in email_duplicado.output
    assert apelido_duplicado.exit_code == 1
    assert "Este apelido já está cadastrado." in apelido_duplicado.output
    assert telefone_duplicado.exit_code == 1
    assert "Este telefone já está cadastrado." in telefone_duplicado.output
    assert email_vazio.exit_code == 1
    assert "e-mail não pode ficar vazio" in email_vazio.output
    assert telefone_vazio.exit_code == 1
    db_session.expire_all()
    alvo = db_session.scalar(select(Usuario).where(Usuario.id == alvo.id))
    assert alvo is not None
    assert alvo.email == "ana.nova@example.com"
    assert alvo.telefone == "31999999999"
    assert alvo.nome == "Ana Atualizada"
    assert alvo.apelido == "Aninha"


def test_desativacao_preserva_historico_e_reativacao_nao_restaura_futuro(
    client, db_session, monkeypatch
):
    configurar_cli(monkeypatch, db_session)
    hoje_teste = date(2026, 9, 28)
    monkeypatch.setattr("app.cli.hoje", lambda: hoje_teste)
    monkeypatch.setattr("app.rotas.inicio.hoje", lambda: hoje_teste)
    monkeypatch.setattr("app.rotas.calendario.hoje", lambda: hoje_teste)
    alvo = criar(db_session, apelido="Historico")
    visualizador = criar(
        db_session,
        email="visualizador@example.com",
        nome="Visualizador",
        apelido="Visualizador",
    )
    token_alvo = "sessao-alvo-desativacao"
    token_visualizador = "sessao-visualizador"
    db_session.add_all(
        [
            Sessao(
                usuario_id=alvo.id,
                token_hash=hash_token(token_alvo),
                csrf_token="csrf-alvo",
                expira_em=datetime.now(timezone.utc) + timedelta(days=1),
            ),
            Sessao(
                usuario_id=visualizador.id,
                token_hash=hash_token(token_visualizador),
                csrf_token="csrf-visualizador",
                expira_em=datetime.now(timezone.utc) + timedelta(days=1),
            ),
        ]
    )
    data_passada = date(2026, 9, 27)
    data_hoje = hoje_teste
    data_futura = date(2026, 9, 29)
    db_session.add_all(
        [
            Marcacao(
                usuario_id=alvo.id,
                data=data,
                status=StatusMarcacao.DISPONIVEL,
            )
            for data in (data_passada, data_hoje, data_futura)
        ]
    )
    db_session.flush()

    cancelado = runner.invoke(
        cli_app,
        ["deactivate-user", "--telefone", alvo.telefone],
        input="n\n",
    )
    assert cancelado.exit_code == 0
    db_session.refresh(alvo)
    assert alvo.ativo

    desativado = runner.invoke(
        cli_app,
        ["deactivate-user", "--telefone", alvo.telefone],
        input="y\n",
    )
    assert desativado.exit_code == 0
    assert "sessões encerradas" in desativado.output
    db_session.expire_all()
    alvo = db_session.scalar(select(Usuario).where(Usuario.email == alvo.email))
    assert alvo is not None and not alvo.ativo
    marcacoes_apos_desativar = list(
        db_session.scalars(
            select(Marcacao).where(Marcacao.usuario_id == alvo.id)
        ).all()
    )
    assert {marcacao.data for marcacao in marcacoes_apos_desativar} == {data_passada}
    assert db_session.scalar(
        select(Sessao.id).where(Sessao.usuario_id == alvo.id)
    ) is None

    client.cookies.set("sessao", token_visualizador)
    with TestClient(web_app) as navegador_alvo:
        navegador_alvo.cookies.set("sessao", token_alvo)
        desconectado = navegador_alvo.get("/", follow_redirects=False)
        grade = client.get("/?mes=2026-09")
        painel = client.get(f"/dias/{data_passada.isoformat()}")
    assert desconectado.status_code == 303
    assert "Historico" in grade.text
    assert "Historico" in painel.text

    reativado = runner.invoke(
        cli_app,
        ["reactivate-user", "--telefone", alvo.telefone],
    )
    assert reativado.exit_code == 0
    db_session.expire_all()
    alvo = db_session.scalar(
        select(Usuario).where(Usuario.email == "ana@example.com")
    )
    assert alvo is not None and alvo.ativo
    marcacoes_restantes = list(
        db_session.scalars(
            select(Marcacao).where(Marcacao.usuario_id == alvo.id)
        ).all()
    )
    assert [marcacao.data for marcacao in marcacoes_restantes] == [data_passada]
