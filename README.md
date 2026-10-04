# Calendário Coop

Calendário compartilhado para indicar disponibilidade por dia. A aplicação usa FastAPI, PostgreSQL 18, HTMX e Caddy para servir HTTPS.

## Pré-requisitos

- Docker Engine com o plugin Docker Compose.
- Para uso público: um domínio com registro A ou AAAA apontando para o IP do servidor.
- No servidor público, as portas TCP 80 e 443 devem estar livres e liberadas no firewall.

O serviço da aplicação não publica a porta 8000 no host. O Caddy recebe as conexões nas portas 80/443 e encaminha para `app:8000` pela rede interna do Compose.

## Uso local

Copie `.env.example` para `.env` e ajuste `DOMINIO` para `localhost`, `CADDY_BIND_ADDRESS` para `127.0.0.1`, a senha do PostgreSQL e as URLs do banco para usarem essa mesma senha. Mantenha `COOKIE_SECURE=true`; o Caddy local serve HTTPS com um certificado da autoridade local.

Suba os serviços:

```bash
docker compose up -d --build
```

Com `DOMINIO=localhost`, o Caddy cria um certificado local. Confira a aplicação com:

```bash
curl -k https://localhost/health
```

O `-k` é necessário enquanto o certificado da autoridade local do Caddy não estiver instalado como confiável no sistema.

## Primeiro deploy público

1. Configure o DNS do domínio para o IP do VPS e libere TCP 80/443 no firewall.
2. Copie `.env.example` para `.env`; defina o domínio real, `CADDY_BIND_ADDRESS=0.0.0.0` para publicar as portas no VPS, uma senha forte para o banco e replique essa senha em `DATABASE_URL` e `TEST_DATABASE_URL`. Mantenha `COOKIE_SECURE=true`.
3. Na pasta do projeto no VPS, rode:

```bash
docker compose up -d --build
```

O Caddy solicita e renova o certificado TLS automaticamente. A app executa `alembic upgrade head` antes de iniciar o Uvicorn.

Crie o primeiro usuário. O comando pedirá a senha em prompt oculto:

```bash
docker compose exec app calendario create-user \
  --email ana@exemplo.com \
  --telefone 31999999999 \
  --nome "Ana Souza" \
  --apelido Ana
```

Na tela `/login`, a pessoa pode entrar usando o e-mail ou o telefone brasileiro
(DDD com dois dígitos e telefone com nove dígitos), junto com a senha.

## Atualizar somente a aplicação

Após atualizar os arquivos ou obter a nova versão do projeto:

```bash
docker compose up -d --build app
```

Esse comando reconstrói e recria somente a app; o container `db` permanece em execução. As migrações são aplicadas no início da app.

## Backup manual do banco

O banco não publica uma porta no host. Gere um dump pelo próprio container e grave o arquivo no host:

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "backup_$(date +%F).dump"
```

Guarde os arquivos de backup fora do servidor e teste periodicamente a restauração.

## Comandos administrativos

```bash
docker compose exec app calendario list-users
docker compose exec app calendario reset-password --telefone 31999999999
docker compose exec app calendario update-user --email ana@exemplo.com --novo-telefone 31988888888
docker compose exec app calendario deactivate-user --telefone 31988888888
docker compose exec app calendario reactivate-user --telefone 31988888888
```

`create-user` exige `--email` e `--telefone`. Nos comandos de manutenção,
informe exatamente um identificador: `--email` ou `--telefone`. Telefones são
normalizados para 11 dígitos antes de serem armazenados ou consultados.

## Testes

Os testes usam o Postgres 18 indicado em `TEST_DATABASE_URL`. Como o `TestClient` usa HTTP, desative `Secure` apenas no processo de teste:

```bash
docker compose exec -e COOKIE_SECURE=false app pytest
```
