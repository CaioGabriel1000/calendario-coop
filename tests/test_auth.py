from datetime import datetime, timedelta, timezone
import re

from sqlalchemy import select

from app.auth import hash_token
from app.models import Sessao, Usuario
from app.senhas import gerar_hash
from app.usuarios import criar_usuario


def preparar_usuario(
    db_session,
    *,
    email="ana@example.com",
    apelido="Ana",
    senha="senha-segura",
    ativo=True,
):
    usuario = Usuario(
        email=email,
        nome="Ana Souza",
        apelido=apelido,
        senha_hash=gerar_hash(senha),
        ativo=ativo,
    )
    db_session.add(usuario)
    db_session.flush()
    return usuario


def csrf_do_login(client):
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert token is not None
    return token.group(1)


def fazer_login(client, email="ana@example.com", senha="senha-segura"):
    csrf_token = csrf_do_login(client)
    return client.post(
        "/login",
        data={"email": email, "senha": senha, "csrf_token": csrf_token},
        follow_redirects=False,
    )


def test_login_correto_cria_sessao_e_mostra_apelido(client, db_session):
    criar_usuario(
        db_session,
        email="ana@example.com",
        nome="Ana Souza",
        apelido="Ana",
        senha="senha-segura",
    )

    response = fazer_login(client)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "sessao" in response.cookies
    token = response.cookies["sessao"]
    sessao = db_session.scalar(select(Sessao))
    assert sessao is not None
    assert sessao.token_hash == hash_token(token)
    assert sessao.token_hash != token
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    pagina = client.get("/", follow_redirects=False)
    assert pagina.status_code == 200
    assert "Ana" in pagina.text
    assert 'id="grade-container"' in pagina.text


def test_credenciais_invalidas_e_usuario_desativado_usam_mesmo_erro(client, db_session):
    preparar_usuario(db_session)
    preparar_usuario(
        db_session,
        email="desativada@example.com",
        apelido="Desativada",
        ativo=False,
    )

    senha_errada = fazer_login(client, senha="incorreta")
    usuario_inativo = fazer_login(
        client,
        email="desativada@example.com",
        senha="senha-segura",
    )
    usuario_desconhecido = fazer_login(
        client,
        email="desconhecida@example.com",
        senha="senha-segura",
    )

    assert senha_errada.status_code == 200
    assert usuario_inativo.status_code == 200
    assert usuario_desconhecido.status_code == 200
    assert "E-mail ou senha inválidos." in senha_errada.text
    assert "E-mail ou senha inválidos." in usuario_inativo.text
    assert "E-mail ou senha inválidos." in usuario_desconhecido.text


def test_usuario_sem_sessao_e_redirecionado_para_login(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_requisicao_htmx_sem_sessao_recebe_hx_redirect(client):
    response = client.get(
        "/",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert response.headers["HX-Redirect"] == "/login"


def test_sessao_expirada_e_recusada(client, db_session):
    usuario = preparar_usuario(db_session)
    token = "token-expirado-de-teste"
    db_session.add(
        Sessao(
            usuario_id=usuario.id,
            token_hash=hash_token(token),
            csrf_token="csrf-token",
            expira_em=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    db_session.flush()

    client.cookies.set("sessao", token)
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_logout_invalida_sessao_e_exige_csrf(client, db_session):
    preparar_usuario(db_session)
    login = fazer_login(client)
    assert login.status_code == 303
    pagina = client.get("/", follow_redirects=False)
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text)
    assert csrf_token is not None

    logout_sem_csrf = client.post(
        "/logout",
        data={"csrf_token": "token-invalido"},
        follow_redirects=False,
    )
    assert logout_sem_csrf.status_code == 403
    assert client.get("/", follow_redirects=False).status_code == 200

    logout = client.post(
        "/logout",
        data={"csrf_token": csrf_token.group(1)},
        follow_redirects=False,
    )

    assert logout.status_code == 303
    assert logout.headers["location"] == "/login"
    pagina_protegida = client.get("/", follow_redirects=False)
    assert pagina_protegida.status_code == 303
    assert pagina_protegida.headers["location"] == "/login"
