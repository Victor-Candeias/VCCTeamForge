"""Teste de carga da API do VCCTeamForge (DEV-025), só com a biblioteca padrão.

Simula ``--users`` utilizadores em simultâneo durante ``--duration`` segundos, cada um com a
sua sessão e ligação keep-alive, a percorrer um cenário ponderado de leituras (dashboard, listas
e pesquisa de issues, quadro, detalhe/comentários/histórico, sprints, relatórios) e,
com ``--write``, comentários. No fim mostra pedidos, erros e latências (p50/p95/p99/máx.) por
operação e falha (código 1) se o p95 global ou a taxa de erros ultrapassarem os limites.

Exemplo (a partir de ``backend/``)::

    VCCTF_LOADTEST_PASSWORD=... python tools/loadtest.py --url http://127.0.0.1:5000 \\
        --email carga@empresa.local --users 10 --duration 120 --project ALFA

Usar uma conta e, de preferência, um projeto dedicados: ``--seed-issues`` e ``--write`` criam
dados reais (com o prefixo ``[carga]``). Todos os utilizadores virtuais usam a mesma conta.
"""

import argparse
import getpass
import http.client
import json
import math
import os
import random
import ssl
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlencode, urlsplit

PASSWORD_ENV = "VCCTF_LOADTEST_PASSWORD"  # noqa: S105 (nome da variável, não o segredo)
CSRF_COOKIE = "vcctf_csrf"
REQUEST_TIMEOUT_SECONDS = 30
SEED_TYPES = ("task", "story", "improvement")
SEARCH_TERMS = ("teste", "erro", "login", "carga", "api")
REPORTABLE_SPRINT_STATUSES = frozenset({"active", "closed"})


class LoadTestError(Exception):
    pass


@dataclass
class Stats:
    latencies: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    error_samples: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, name: str, elapsed: float, error: str | None) -> None:
        with self.lock:
            self.latencies[name].append(elapsed)
            if error is not None:
                self.errors[name] += 1
                if len(self.error_samples) < 10:
                    self.error_samples.append(f"{name}: {error}")

    @property
    def total(self) -> int:
        return sum(len(values) for values in self.latencies.values())

    @property
    def total_errors(self) -> int:
        return sum(self.errors.values())


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[max(math.ceil(fraction * len(ordered)) - 1, 0)]


class Session:
    """Ligação keep-alive com cookies e cabeçalho CSRF, como o frontend."""

    def __init__(self, base_url: str, *, insecure: bool = False) -> None:
        parts = urlsplit(base_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise LoadTestError(f"URL inválido: {base_url}")
        self.scheme = parts.scheme
        self.host = parts.hostname
        self.port = parts.port
        self.prefix = parts.path.rstrip("/")
        self.context = ssl._create_unverified_context() if insecure else None  # noqa: S323
        self.cookies: dict[str, str] = {}
        self.connection: http.client.HTTPConnection | None = None

    def _connect(self) -> http.client.HTTPConnection:
        if self.connection is None:
            if self.scheme == "https":
                self.connection = http.client.HTTPSConnection(
                    self.host, self.port, timeout=REQUEST_TIMEOUT_SECONDS, context=self.context
                )
            else:
                self.connection = http.client.HTTPConnection(
                    self.host, self.port, timeout=REQUEST_TIMEOUT_SECONDS
                )
        return self.connection

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def request(
        self, method: str, path: str, *, params: dict | None = None, body: Any = None
    ) -> tuple[int, Any]:
        url = self.prefix + path + (f"?{urlencode(params, doseq=True)}" if params else "")
        headers = {"Accept": "application/json"}
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        if method not in {"GET", "HEAD"} and CSRF_COOKIE in self.cookies:
            headers["X-CSRF-Token"] = self.cookies[CSRF_COOKIE]
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        for attempt in (1, 2):
            connection = self._connect()
            try:
                connection.request(method, url, body=payload, headers=headers)
                response = connection.getresponse()
                data = response.read()
                break
            except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
                # Ligação keep-alive fechada pelo servidor entretanto: repetir uma vez.
                self.close()
                if attempt == 2:
                    raise
        for header in response.headers.get_all("Set-Cookie") or []:
            for name, morsel in SimpleCookie(header).items():
                if morsel.value:
                    self.cookies[name] = morsel.value
                else:
                    self.cookies.pop(name, None)
        content_type = response.headers.get("Content-Type", "")
        parsed = json.loads(data) if data and content_type.startswith("application/json") else data
        return response.status, parsed

    def login(self, email: str, password: str) -> None:
        status, _ = self.request("GET", "/api/auth/csrf")
        if status != 200:
            raise LoadTestError(f"GET /api/auth/csrf devolveu {status}")
        status, body = self.request(
            "POST", "/api/auth/login", body={"email": email, "password": password}
        )
        if status != 200:
            detail = body.get("detail") if isinstance(body, dict) else body
            raise LoadTestError(f"Login falhou ({status}): {detail}")


@dataclass
class Target:
    project_id: str
    project_key: str
    issue_ids: list[str]
    sprint_ids: list[str]


def discover(session: Session, project_key: str | None) -> Target:
    status, page = session.request("GET", "/api/projects", params={"pageSize": 100})
    if status != 200:
        raise LoadTestError(f"GET /api/projects devolveu {status}")
    projects = page["items"]
    if project_key:
        projects = [p for p in projects if p["key"].upper() == project_key.upper()]
    if not projects:
        raise LoadTestError("Nenhum projeto acessível (ou --project inexistente)")
    project = projects[0]
    _, issues = session.request(
        "GET", "/api/issues", params={"projectId": project["id"], "pageSize": 100}
    )
    _, sprints = session.request(
        "GET", "/api/sprints", params={"projectId": project["id"], "pageSize": 100}
    )
    return Target(
        project_id=project["id"],
        project_key=project["key"],
        issue_ids=[issue["id"] for issue in issues.get("items", [])],
        # O relatório só existe para sprints iniciadas (planeadas devolvem 422).
        sprint_ids=[
            sprint["id"]
            for sprint in sprints.get("items", [])
            if sprint["status"] in REPORTABLE_SPRINT_STATUSES
        ],
    )


def seed_issues(session: Session, target: Target, count: int) -> None:
    for number in range(1, count + 1):
        status, body = session.request(
            "POST",
            "/api/issues",
            body={
                "projectId": target.project_id,
                "type": SEED_TYPES[number % len(SEED_TYPES)],
                "title": f"[carga] Issue de teste {number}",
            },
        )
        if status != 201:
            raise LoadTestError(f"Criação de issue falhou ({status}): {body}")
        target.issue_ids.append(body["id"])


Request = tuple[str, str, dict, Any]
Operation = tuple[str, int, Callable[[Target, random.Random], Request]]


def operations(write: bool) -> list[Operation]:
    """Cenário ponderado (nome, peso, pedido), próximo da utilização real do frontend."""
    ops: list[Operation] = [
        ("dashboard", 2, lambda t, r: ("GET", "/api/dashboard/overview", {}, None)),
        ("projetos", 1, lambda t, r: ("GET", "/api/projects", {}, None)),
        (
            "issues.lista",
            4,
            lambda t, r: ("GET", "/api/issues", {"projectId": t.project_id, "page": 1}, None),
        ),
        (
            "issues.pesquisa",
            2,
            lambda t, r: (
                "GET",
                "/api/issues",
                {"projectId": t.project_id, "q": r.choice(SEARCH_TERMS)},
                None,
            ),
        ),
        ("quadro", 3, lambda t, r: ("GET", f"/api/projects/{t.project_id}/board", {}, None)),
        ("sprints", 1, lambda t, r: ("GET", "/api/sprints", {"projectId": t.project_id}, None)),
        (
            "metricas",
            1,
            lambda t, r: ("GET", f"/api/reports/projects/{t.project_id}/metrics", {}, None),
        ),
        (
            "issue.detalhe",
            3,
            lambda t, r: ("GET", f"/api/issues/{r.choice(t.issue_ids)}", {}, None),
        ),
        (
            "issue.comentarios",
            1,
            lambda t, r: ("GET", f"/api/issues/{r.choice(t.issue_ids)}/comments", {}, None),
        ),
        (
            "issue.historico",
            1,
            lambda t, r: ("GET", f"/api/issues/{r.choice(t.issue_ids)}/history", {}, None),
        ),
        (
            "sprint.relatorio",
            1,
            lambda t, r: ("GET", f"/api/reports/sprints/{r.choice(t.sprint_ids)}", {}, None),
        ),
    ]
    if write:
        ops.append(
            (
                "issue.comentar",
                1,
                lambda t, r: (
                    "POST",
                    f"/api/issues/{r.choice(t.issue_ids)}/comments",
                    {},
                    {"body": "[carga] comentário de teste"},
                ),
            )
        )
    return ops


def available_operations(ops: list[Operation], target: Target) -> list[Operation]:
    """Sem issues ou sprints no projeto, as operações que precisam delas ficam de fora."""
    return [
        op
        for op in ops
        if (target.issue_ids or not op[0].startswith("issue."))
        and (target.sprint_ids or not op[0].startswith("sprint."))
    ]


def run_user(
    base_url: str,
    credentials: tuple[str, str],
    target: Target,
    ops: list[Operation],
    *,
    deadline: float,
    think_time: float,
    seed: int,
    insecure: bool,
    stats: Stats,
) -> None:
    rng = random.Random(seed)  # noqa: S311 (escolha de cenários, não criptografia)
    session = Session(base_url, insecure=insecure)
    started = time.perf_counter()
    try:
        session.login(*credentials)
        stats.record("login", time.perf_counter() - started, None)
    except (LoadTestError, OSError, http.client.HTTPException) as error:
        stats.record("login", time.perf_counter() - started, str(error))
        session.close()
        return
    weights = [op[1] for op in ops]
    try:
        while time.monotonic() < deadline:
            name, _, build = rng.choices(ops, weights)[0]
            method, path, params, body = build(target, rng)
            started = time.perf_counter()
            try:
                status, _ = session.request(method, path, params=params, body=body)
                error = None if 200 <= status < 300 else f"HTTP {status} {method} {path}"
            except (OSError, http.client.HTTPException, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                session.close()
            stats.record(name, time.perf_counter() - started, error)
            if think_time:
                time.sleep(rng.uniform(0, 2 * think_time))
    finally:
        session.close()


def report(stats: Stats, elapsed: float, out: Callable[[str], None]) -> tuple[float, float]:
    """Tabela por operação; devolve o p95 global (ms, sem logins) e a taxa de erros."""
    out(
        f"{'operação':<20}{'pedidos':>9}{'erros':>7}"
        f"{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'máx ms':>9}"
    )
    for name in sorted(stats.latencies):
        values = stats.latencies[name]
        out(
            f"{name:<20}{len(values):>9}{stats.errors.get(name, 0):>7}"
            f"{percentile(values, 0.50) * 1000:>9.0f}{percentile(values, 0.95) * 1000:>9.0f}"
            f"{percentile(values, 0.99) * 1000:>9.0f}{max(values) * 1000:>9.0f}"
        )
    requests = [v for name, values in stats.latencies.items() if name != "login" for v in values]
    p95 = percentile(requests, 0.95) * 1000
    error_rate = stats.total_errors / stats.total if stats.total else 1.0
    out(
        f"Total: {stats.total} pedidos em {elapsed:.1f} s ({stats.total / elapsed:.1f} pedidos/s), "
        f"{stats.total_errors} erro(s) ({error_rate:.2%}), p95 global {p95:.0f} ms"
    )
    for sample in stats.error_samples:
        out(f"  erro: {sample}")
    return p95, error_rate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:5000", help="URL base (sem /api)")
    parser.add_argument("--email", required=True, help=f"Conta de teste (password: {PASSWORD_ENV})")
    parser.add_argument("--project", help="Chave do projeto (por omissão o primeiro acessível)")
    parser.add_argument("--users", type=int, default=10, help="Utilizadores simultâneos")
    parser.add_argument("--duration", type=float, default=60, help="Duração em segundos")
    parser.add_argument("--ramp-up", type=float, default=5, help="Segundos até todos arrancarem")
    parser.add_argument("--think-time", type=float, default=0.5, help="Pausa média entre pedidos")
    parser.add_argument("--write", action="store_true", help="Inclui criação de comentários")
    parser.add_argument("--seed-issues", type=int, default=0, help="Issues a criar antes do teste")
    parser.add_argument("--max-p95-ms", type=float, default=800, help="Limite do p95 global")
    parser.add_argument("--max-error-rate", type=float, default=0.01, help="Limite de erros (0-1)")
    parser.add_argument("--insecure", action="store_true", help="Aceita certificados inválidos")
    parser.add_argument("--seed", type=int, default=1, help="Semente dos cenários aleatórios")
    return parser


def main(argv: list[str] | None = None, out: Callable[[str], None] = print) -> int:
    args = build_parser().parse_args(argv)
    if args.users < 1 or args.duration <= 0 or args.ramp_up < 0:
        out("Erro: --users >= 1, --duration > 0 e --ramp-up >= 0")
        return 2
    password = os.environ.get(PASSWORD_ENV) or getpass.getpass(f"Password de {args.email}: ")
    credentials = (args.email, password)

    setup = Session(args.url, insecure=args.insecure)
    try:
        setup.login(*credentials)
        target = discover(setup, args.project)
        if args.seed_issues:
            out(f"A criar {args.seed_issues} issue(s) em {target.project_key}...")
            seed_issues(setup, target, args.seed_issues)
    except (LoadTestError, OSError, http.client.HTTPException) as error:
        out(f"Erro na preparação: {error}")
        return 1
    finally:
        setup.close()

    ops = available_operations(operations(args.write), target)
    out(
        f"Projeto {target.project_key}: {len(target.issue_ids)} issue(s) e "
        f"{len(target.sprint_ids)} sprint(s) amostradas; {args.users} utilizador(es) durante "
        f"{args.duration:.0f} s ({len(ops)} operações)"
    )
    stats = Stats()
    started = time.monotonic()
    deadline = started + args.ramp_up + args.duration
    threads = []
    for index in range(args.users):
        thread = threading.Thread(
            target=run_user,
            args=(args.url, credentials, target, ops),
            kwargs={
                "deadline": deadline,
                "think_time": args.think_time,
                "seed": args.seed + index,
                "insecure": args.insecure,
                "stats": stats,
            },
            daemon=True,
        )
        thread.start()
        threads.append(thread)
        if args.users > 1:
            time.sleep(args.ramp_up / (args.users - 1))
    for thread in threads:
        thread.join()
    p95, error_rate = report(stats, time.monotonic() - started, out)
    failed = []
    if p95 > args.max_p95_ms:
        failed.append(f"p95 {p95:.0f} ms > {args.max_p95_ms:.0f} ms")
    if error_rate > args.max_error_rate:
        failed.append(f"erros {error_rate:.2%} > {args.max_error_rate:.2%}")
    out("RESULTADO: " + (f"FALHOU ({'; '.join(failed)})" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
