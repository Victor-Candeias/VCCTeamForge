# Deployment do VCCTeamForge

Instalação num servidor Debian/Ubuntu da LAN, com Nginx à frente da API FastAPI e MongoDB 4.4 no mesmo computador (ver `README.md` §8 e §10).

```text
Browsers --> Nginx :80/:443 --+-- /        -> /var/www/VCCTeamForge (frontend/dist)
                              +-- /api/    -> 127.0.0.1:5000 (VCCTeamForge-api.service)
                                                    |
                                                    v
                                             127.0.0.1:27017 (MongoDB 4.4, com autenticação)
```

## Conteúdo

| Ficheiro | Destino no servidor |
|---|---|
| `systemd/VCCTeamForge-api.service` | `/etc/systemd/system/VCCTeamForge-api.service` |
| `nginx/vccteamforge.conf` (HTTP) ou `nginx/vccteamforge-https.conf` (HTTPS) | `/etc/nginx/sites-available/vccteamforge` |
| `nginx/vccteamforge-locations.conf`, `nginx/vccteamforge-security-headers.conf` | `/etc/nginx/snippets/` |
| `env/api.env.example` | `/etc/VCCTeamForge/api.env` (`root:vccteamforge`, `0640`) |
| `scripts/vccteamforge-manage` | `/usr/local/sbin/vccteamforge-manage` |
| `scripts/install.sh` | preparação única do servidor (root) |
| `scripts/build-frontend.sh` | compila `frontend/dist` (utilizador normal) |
| `scripts/deploy.sh` | publica uma versão (root) |

Layout no servidor:

| Caminho | Dono | Conteúdo |
|---|---|---|
| `/opt/VCCTeamForge/backend`, `database`, `deployment` | `root` (só leitura para o serviço) | código copiado do repositório |
| `/opt/VCCTeamForge/venv` | `root` | virtualenv com `backend/requirements.txt` |
| `/etc/VCCTeamForge/api.env` | `root:vccteamforge` `0640` | configuração e segredos |
| `/var/lib/VCCTeamForge/attachments` | `vccteamforge` `0750` | anexos (`StateDirectory`) |
| `/var/www/VCCTeamForge` | `root` | frontend estático |

A API corre a partir do código-fonte (`WorkingDirectory=/opt/VCCTeamForge/backend`, `python -m app`); o pacote não é instalado no venv. Os logs vão para o journald (`journalctl -u VCCTeamForge-api`).

## Pré-requisitos

- Python ≥ 3.11 com `python3-venv`, `nginx`, `rsync`, `curl`; Node.js 24 (apenas na máquina que compila o frontend).
- MongoDB 4.4 com `security.authorization: enabled` e `net.bindIp: 127.0.0.1`. A unidade assume o serviço `mongodb44.service`; ajustar `After=`/`Wants=` se o nome for outro.

## Primeira instalação

1. **Utilizador MongoDB da aplicação** (permissões mínimas), com um administrador:

   ```javascript
   use VCCTeamForgeDB
   db.createUser({ user: "VCCTeamForge_app", pwd: passwordPrompt(), roles: [{ role: "readWrite", db: "VCCTeamForgeDB" }] })
   ```

2. **Preparar o servidor** a partir de um clone do repositório:

   ```bash
   sudo deployment/scripts/install.sh            # Nginx em HTTP
   sudo deployment/scripts/install.sh --https    # Nginx em HTTPS (recomendado)
   ```

   Cria o utilizador de sistema `vccteamforge`, as diretorias acima, instala a unidade systemd, o site Nginx (desativando o site `default`) e o `vccteamforge-manage`. Não sobrescreve um `api.env` existente.

3. **Configurar** `/etc/VCCTeamForge/api.env` (`sudoedit`): `MONGODB_PASSWORD` e, se o Nginx servir HTTP simples, `COOKIE_SECURE=false` (sem isto o browser não envia o cookie de sessão por HTTP). Com HTTPS, colocar o certificado e a chave em `/etc/ssl/vccteamforge/` (ou ajustar os caminhos) e o `server_name`.

4. **Compilar e publicar**:

   ```bash
   deployment/scripts/build-frontend.sh
   sudo deployment/scripts/deploy.sh
   ```

5. **Primeiro administrador**:

   ```bash
   sudo vccteamforge-manage create-user --email admin@empresa.local --name "Administrador" --role admin
   ```

6. **Firewall**: abrir apenas 80/443 à sub-rede autorizada; 5000 e 27017 ficam no loopback. Exemplo com `ufw`:

   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 443 proto tcp
   ```

## Atualizações

```bash
git pull
deployment/scripts/build-frontend.sh
sudo deployment/scripts/deploy.sh
```

`deploy.sh` copia o código para `/opt/VCCTeamForge`, atualiza o venv, pré-compila o bytecode, aplica migrations e seeds (`vccteamforge-manage migrate|seed`), reinicia a API, espera por `GET /api/health/ready` (falha com o estado e os últimos logs ao fim de 60 s), publica o frontend (assets primeiro, `index.html` no fim) e recarrega o Nginx após `nginx -t`. Alterações a ficheiros de systemd/Nginx exigem voltar a correr `install.sh`.

## Operação

| Ação | Comando |
|---|---|
| Estado da API | `systemctl status VCCTeamForge-api` |
| Logs da API | `journalctl -u VCCTeamForge-api -f` |
| Readiness | `curl -s http://127.0.0.1:5000/api/health/ready` |
| Estado da BD (migrations/índices) | `sudo vccteamforge-manage status` |
| Anexos órfãos ou em falta no disco | `sudo vccteamforge-manage attachments-check` |
| Logs do Nginx | `/var/log/nginx/vccteamforge.{access,error}.log` (com `rid=` igual ao `X-Request-ID`) |

## Deploy local sem root (`deploy-local.sh`)

Alternativa para uma máquina sem Nginx nem acesso root: publica backend + frontend em `/opt/vccteamforge` e gere-os como serviços `systemd --user`.

```bash
sudo install -d -o "$USER" /opt/vccteamforge   # só na primeira vez
deployment/scripts/deploy-local.sh
sudo loginctl enable-linger "$USER"              # opcional: arrancar no boot e sobreviver ao logout
sudo ufw allow from 192.168.1.0/24 to any port 5175 proto tcp   # se o ufw estiver ativo (ajustar a sub-rede)
```

O script copia o código, atualiza o venv e o `node_modules` (só quando `requirements.txt`/`package-lock.json` mudam), compila o frontend (troca o `dist` apenas se o build tiver sucesso), aplica migrations e seeds e reinicia os dois serviços, esperando pelo readiness de cada um.

| Componente | Serviço | Escuta |
|---|---|---|
| API | `vccteamforge-api.service` | `127.0.0.1:5100` |
| Frontend (`vite preview`, proxy de `/api` para a API) | `vccteamforge-web.service` | `0.0.0.0:5175` (acessível na LAN) |

- Configuração em `/opt/vccteamforge/config/api.env` (`0600`), criada na primeira execução a partir de `env/api.env.example`, com as credenciais `MONGODB_*` do `.env` da raiz do repositório e `COOKIE_SECURE=false` (HTTP). Não é sobrescrita depois.
- Anexos em `/opt/vccteamforge/data/attachments`.
- Variáveis opcionais: `VCCTF_DEPLOY_ROOT`, `VCCTF_API_PORT` (só na criação do `api.env`), `VCCTF_WEB_PORT`, `VCCTF_ALLOWED_HOSTS` (nomes aceites pelo frontend além de IPs e `localhost`; por omissão o nome da máquina).
- Operação: `systemctl --user status vccteamforge-api vccteamforge-web`, `journalctl --user -u vccteamforge-api -u vccteamforge-web -f`; CLI: `cd /opt/vccteamforge/backend && VCCTF_ENV_FILE=/opt/vccteamforge/config/api.env ../venv/bin/python -m app.cli status`.
- Sem Nginx não há TLS nem os cabeçalhos de segurança do snippet; usar apenas numa rede de confiança.

## Notas de segurança

- A unidade systemd corre sem privilégios, com o sistema de ficheiros só de leitura (`ProtectSystem=strict`) exceto `/var/lib/VCCTeamForge`, filtro de syscalls, `MemoryDenyWriteExecute` e limite de 512 MiB (`systemd-analyze security` ≈ 1.2).
- O Nginx substitui `X-Forwarded-For` pelo IP do cliente (não confia no valor enviado), o que protege o rate limiting de login; a API só confia em cabeçalhos de proxy vindos de `127.0.0.1` (`FORWARDED_ALLOW_IPS`).
- Cabeçalhos de segurança (CSP sem scripts inline, `X-Frame-Options`, `nosniff`, `Referrer-Policy`) aplicados a todas as respostas; `/api/docs` só a partir do próprio servidor (e desativado em produção por omissão).
- Se `VCCTF_ENV_FILE` apontar para um ficheiro inexistente, a API recusa arrancar em vez de usar a configuração por omissão.
- HSTS está comentado na variante HTTPS: ativar só quando o certificado for confiável em todos os postos.
