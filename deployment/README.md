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
| `systemd/VCCTeamForge-report-snapshots.{service,timer}` | `/etc/systemd/system/` (snapshot diário dos KPIs) |
| `systemd/VCCTeamForge-backup.{service,timer}` | `/etc/systemd/system/` (backup diário da BD e dos anexos) |
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
| `/var/backups/VCCTeamForge` | `vccteamforge` `0750` | backups `.tar.gz` (`0600`) |
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

   Cria o utilizador de sistema `vccteamforge`, as diretorias acima, instala as unidades systemd (API e os timers dos snapshots diários e do backup diário, que ficam ativos), o site Nginx (desativando o site `default`) e o `vccteamforge-manage`. Não sobrescreve um `api.env` existente.

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
| Snapshots diários dos KPIs (tendências) | `systemctl list-timers VCCTeamForge-report-snapshots`; manual: `sudo vccteamforge-manage report-snapshots` |
| Backup diário (02:30) | `systemctl list-timers VCCTeamForge-backup`; manual: `sudo systemctl start VCCTeamForge-backup` ou `sudo vccteamforge-manage backup` |
| Verificar um backup | `sudo vccteamforge-manage backup-verify /var/backups/VCCTeamForge/<arquivo>.tar.gz` |
| Restaurar | ver [Backups e restauro](#backups-e-restauro) |
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
- Snapshots diários dos KPIs: `vccteamforge-report-snapshots.timer` (23:50 UTC, `Persistent=true`); ver com `systemctl --user list-timers`.
- Backups diários em `/opt/vccteamforge/backups` (`vccteamforge-backup.timer`, 02:30). O script acrescenta `BACKUP_PATH` a um `api.env` que ainda não o tenha.
- Operação: `systemctl --user status vccteamforge-api vccteamforge-web`, `journalctl --user -u vccteamforge-api -u vccteamforge-web -f`; CLI: `cd /opt/vccteamforge/backend && VCCTF_ENV_FILE=/opt/vccteamforge/config/api.env ../venv/bin/python -m app.cli status`.
- Sem Nginx não há TLS nem os cabeçalhos de segurança do snippet; usar apenas numa rede de confiança.

## Backups e restauro

O `VCCTeamForge-backup.timer` corre `app.cli backup` todos os dias às 02:30 (hora local; `Persistent=true` recupera uma execução perdida com a máquina desligada). Cada execução:

- escreve `vccteamforge-backup-<AAAAMMDDTHHMMSSZ>.tar.gz` (`0600`) em `BACKUP_PATH`, primeiro como `.partial` e só no fim com o nome final, pelo que um backup interrompido nunca parece válido;
- inclui todas as collections em BSON (tipos preservados), com opções (validadores) e índices, mais todos os ficheiros de anexos e um `manifest.json` com SHA-256 e tamanho de cada membro. De `sessions`, `login_attempts` e `maintenance_locks` guarda só a estrutura;
- mantém os `BACKUP_RETENTION` (14) backups mais recentes e apaga os anteriores;
- corre com prioridade baixa de CPU e disco. Não pára a API: a cópia não é um snapshot atómico, pelo que alterações feitas durante os segundos do backup podem ficar apenas em parte.

`sudo vccteamforge-manage status` mostra o último backup e a sua idade. Falhas aparecem em `systemctl status VCCTeamForge-backup` e `journalctl -u VCCTeamForge-backup`.

**Cópia para outro dispositivo.** Um backup no mesmo disco não protege contra a perda do servidor. Copiar a partir de outra máquina (modelo *pull*, sem dar ao servidor credenciais para outro destino), por exemplo diariamente às 04:00:

```bash
rsync -a --delete servidor:/var/backups/VCCTeamForge/ /mnt/backups/vccteamforge/
```

O utilizador remoto precisa de leitura em `/var/backups/VCCTeamForge` (por exemplo, membro do grupo `vccteamforge`). Os arquivos contêm os hashes Argon2id das passwords e todos os dados: guardá-los fora do servidor só em suporte cifrado (LUKS, disco cifrado ou `gpg --symmetric`).

**Restauro** (substitui toda a BD e os anexos; as sessões são terminadas):

```bash
sudo systemctl stop VCCTeamForge-report-snapshots.timer VCCTeamForge-backup.timer VCCTeamForge-api
sudo vccteamforge-manage backup-verify /var/backups/VCCTeamForge/<arquivo>.tar.gz
sudo vccteamforge-manage restore /var/backups/VCCTeamForge/<arquivo>.tar.gz --yes
sudo vccteamforge-manage migrate             # se o backup for de uma versão anterior
sudo vccteamforge-manage attachments-check
sudo systemctl start VCCTeamForge-api VCCTeamForge-report-snapshots.timer VCCTeamForge-backup.timer
```

O `restore` verifica o arquivo inteiro (checksums, nomes, contagens) e o espaço livre antes de alterar qualquer dado. Cria depois um backup de segurança do estado atual (`vccteamforge-pre-restore-*.tar.gz`, fora da retenção; apagar à mão quando já não for preciso). Restaura então as collections e, só no fim, troca os anexos. Se falhar a meio, a mensagem indica o comando para repor o backup de segurança. Para restaurar noutra máquina, copiar o arquivo para `/var/backups/VCCTeamForge` (`vccteamforge`, `0600`) e seguir os mesmos passos depois de `install.sh` e `deploy.sh`.

**Objetivos:**

| | Objetivo | Medido (DEV-025) |
|---|---|---|
| RPO (dados que se podem perder) | ≤ 24 h (backup diário) | — |
| Backup | — | 7 s para ~6 700 documentos e 50 MiB de anexos (arquivo de 50 MiB) |
| Restauro (só o comando) | — | 12 s para o mesmo volume, incluindo o backup de segurança |
| RTO (até a API voltar a responder) | ≤ 1 h com o servidor disponível; ≤ 4 h a partir de uma máquina nova | — |

Medições num portátil de 4 núcleos, 1,9 GB de RAM e armazenamento eMMC, com MongoDB 4.4.

**Teste periódico de restauro** (mensal e depois de cada atualização do MongoDB ou da aplicação):

1. `backup-verify` do backup mais recente, tanto no servidor como na cópia externa.
2. Restauro completo numa máquina de teste (ou num deploy local com `deploy-local.sh`), seguido de `status`, `attachments-check`, login e abertura de um anexo. Registar a duração para atualizar o RTO medido.

## Carga e recursos

`backend/tools/loadtest.py` (só a biblioteca padrão; copiado para `/opt/VCCTeamForge/backend/tools`) simula utilizadores com sessão própria. Cada utilizador faz login e percorre o dashboard, as listas e a pesquisa de issues, o quadro, as sprints, as métricas, o detalhe e o histórico das issues e o relatório de sprint; com `--write`, também cria comentários. No fim, mostra p50/p95/p99 por operação e devolve um código de saída diferente de zero se o p95 ou a taxa de erros excederem os limites.

```bash
export VCCTF_LOADTEST_PASSWORD='...'   # conta de teste (não usar um administrador real)
/opt/VCCTeamForge/venv/bin/python /opt/VCCTeamForge/backend/tools/loadtest.py \
  --url https://vccteamforge.local --insecure --email carga@empresa.local --project DEMO \
  --users 20 --duration 120 --think-time 3 --write
```

`--seed-issues N` cria N issues antes de começar. Não correr contra produção com `--write`/`--seed-issues`; usar uma cópia restaurada. Através do Nginx, todos os utilizadores simulados partilham o IP do posto que corre o teste e, por isso, o limite de 20 pedidos/s (burst 40) de `limit_req`: perfis mais intensos que o uso normal devem ir diretamente à API (`--url http://127.0.0.1:5000`, no servidor).

Medições (1 worker, ~2 000 issues, 50 anexos, mesma máquina):

| Perfil | Pedidos/s | p95 global | Mais lento (p95) | Erros | RSS máx. da API |
|---|---|---|---|---|---|
| 20 utilizadores, pausa média 3 s (uso normal) | 6,3 | 520 ms | quadro 721 ms | 0 | 173 MiB |
| 20 utilizadores, pausa média 0,5 s (stress) | 19,2 | 1 172 ms | quadro 1 548 ms, métricas 1 490 ms | 0 | 275 MiB |

Com uso normal fica dentro do limite por omissão (p95 ≤ 800 ms). Se o uso real se aproximar do perfil de stress, aumentar `APP_WORKERS` para 2 (cada worker usa até ~280 MiB, por isso subir também o `MemoryMax`).

Acompanhar os recursos durante o teste e em produção:

- `systemctl status VCCTeamForge-api` (memória atual face ao `MemoryMax=512M`) e `systemd-cgtop`;
- `journalctl -u VCCTeamForge-api` para erros 5xx e pedidos lentos;
- `curl -s http://127.0.0.1:5000/api/health/ready` (estado do MongoDB e espaço livre em disco);
- `df -h /var/lib/VCCTeamForge /var/backups/VCCTeamForge` (anexos e backups crescem com o tempo).

## Notas de segurança

- A unidade systemd corre sem privilégios, com o sistema de ficheiros só de leitura (`ProtectSystem=strict`) exceto `/var/lib/VCCTeamForge`, filtro de syscalls, `MemoryDenyWriteExecute` e limite de 512 MiB (`systemd-analyze security` ≈ 1.2).
- O Nginx substitui `X-Forwarded-For` pelo IP do cliente (não confia no valor enviado), o que protege o rate limiting de login; a API só confia em cabeçalhos de proxy vindos de `127.0.0.1` (`FORWARDED_ALLOW_IPS`).
- Cabeçalhos de segurança (CSP sem scripts inline, `X-Frame-Options`, `nosniff`, `Referrer-Policy`) aplicados a todas as respostas; `/api/docs` só a partir do próprio servidor (e desativado em produção por omissão).
- Se `VCCTF_ENV_FILE` apontar para um ficheiro inexistente, a API recusa arrancar em vez de usar a configuração por omissão.
- HSTS está comentado na variante HTTPS: ativar só quando o certificado for confiável em todos os postos.
- Os backups ficam em `0600`/`0750` (dono `vccteamforge`) e contêm os hashes das passwords; a unidade de backup tem o mesmo isolamento da API, com escrita só em `/var/backups/VCCTeamForge`.
- `backend/tests/test_security.py` verifica, para todas as rotas da API, que sem sessão a resposta é 401 e que sem CSRF válido as escritas são recusadas. Revisão de segurança e riscos residuais: spec `dev-025-spec` (`.maestru/`).
