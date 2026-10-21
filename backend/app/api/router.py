from fastapi import APIRouter, Depends

from app.api.deps import verify_csrf
from app.api.routes import (
    admin_users,
    attachments,
    audit,
    auth,
    dashboard,
    health,
    issues,
    projects,
    qa,
    releases,
    reports,
    sprints,
    users,
)

api_router = APIRouter(dependencies=[Depends(verify_csrf)])
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(issues.router)
api_router.include_router(sprints.router)
api_router.include_router(qa.router)
api_router.include_router(releases.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(attachments.router)
api_router.include_router(audit.router)
api_router.include_router(admin_users.router)
