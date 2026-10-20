"""Perfis globais e permissões (README §3).

As permissões por perfil definem o que cada utilizador pode fazer em geral; o acesso a dados de um
projeto exige ainda ser membro desse projeto (ver ``app.services.authorization``).
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    TECH_LEAD = "tech_lead"
    DEVELOPER = "developer"
    QA = "qa"


class Permission(StrEnum):
    USERS_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"
    AUDIT_READ = "audit:read"
    PROJECTS_READ = "projects:read"
    PROJECTS_MANAGE = "projects:manage"
    ISSUES_READ = "issues:read"
    ISSUES_WRITE = "issues:write"
    ISSUES_COMMENT = "issues:comment"
    SPRINTS_MANAGE = "sprints:manage"
    TESTS_READ = "tests:read"
    TESTS_MANAGE = "tests:manage"
    TESTS_EXECUTE = "tests:execute"
    RELEASES_READ = "releases:read"
    RELEASES_MANAGE = "releases:manage"
    RELEASES_APPROVE = "releases:approve"
    REPORTS_READ = "reports:read"


_MEMBER_BASE = frozenset(
    {
        Permission.PROJECTS_READ,
        Permission.ISSUES_READ,
        Permission.ISSUES_COMMENT,
        Permission.TESTS_READ,
        Permission.RELEASES_READ,
        Permission.REPORTS_READ,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.TECH_LEAD: _MEMBER_BASE
    | {
        Permission.PROJECTS_MANAGE,
        Permission.ISSUES_WRITE,
        Permission.SPRINTS_MANAGE,
        Permission.RELEASES_MANAGE,
        Permission.RELEASES_APPROVE,
    },
    # A restrição "apenas issues atribuídas" é uma regra de domínio aplicada nos serviços de issues.
    Role.DEVELOPER: _MEMBER_BASE | {Permission.ISSUES_WRITE},
    # QA cria bugs (issues:write), gere casos de teste e regista execuções.
    Role.QA: _MEMBER_BASE
    | {Permission.ISSUES_WRITE, Permission.TESTS_MANAGE, Permission.TESTS_EXECUTE},
}


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]
