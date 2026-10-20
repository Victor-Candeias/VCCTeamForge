"""Ligação ao MongoDB 4.4 com PyMongo síncrono.

Regras de compatibilidade com MongoDB 4.4:
- não usar transações multi-documento (a instância pode ser standalone);
- não usar operadores/estágios introduzidos depois da 4.4 (ex.: $setWindowFields, $dateTrunc,
  $getField, time-series collections);
- datas sempre em UTC (``tz_aware=True``).
"""

from dataclasses import dataclass

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import Settings

MIN_SERVER_VERSION = (4, 4)
APP_NAME = "VCCTeamForge"


class IncompatibleServerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ServerInfo:
    version: str
    version_tuple: tuple[int, ...]


def create_client(settings: Settings) -> MongoClient:
    """Cria o cliente sem abrir ligação (a ligação é estabelecida no primeiro pedido)."""
    credentials = {}
    if settings.mongodb_username and settings.mongodb_password:
        credentials = {
            "username": settings.mongodb_username,
            "password": settings.mongodb_password.get_secret_value(),
            "authSource": settings.mongodb_auth_source,
        }
    return MongoClient(
        host=settings.mongodb_host,
        port=settings.mongodb_port,
        appname=APP_NAME,
        tz_aware=True,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        connectTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        maxPoolSize=settings.mongodb_max_pool_size,
        connect=False,
        **credentials,
    )


def get_server_info(client: MongoClient) -> ServerInfo:
    build_info = client.admin.command("buildInfo")
    version = str(build_info["version"])
    version_tuple = tuple(int(part) for part in build_info.get("versionArray", [])[:3])
    if not version_tuple:
        version_tuple = tuple(int(part) for part in version.split("-")[0].split(".")[:3])
    return ServerInfo(version=version, version_tuple=version_tuple)


def check_server_compatibility(client: MongoClient) -> ServerInfo:
    info = get_server_info(client)
    if info.version_tuple[:2] < MIN_SERVER_VERSION:
        minimum = ".".join(map(str, MIN_SERVER_VERSION))
        raise IncompatibleServerError(f"MongoDB {info.version} não suportado; mínimo {minimum}")
    return info


def ping(client: MongoClient) -> None:
    client.admin.command("ping")


def get_database(client: MongoClient, settings: Settings) -> Database:
    return client[settings.mongodb_database]
