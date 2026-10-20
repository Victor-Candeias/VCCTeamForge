from fastapi import APIRouter, Depends

from app.api.deps import verify_csrf
from app.api.routes import (
    attachments,
    audit,
    auth,
    health,
    issues,
    projects,
    qa,
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
api_router.include_router(attachments.router)
api_router.include_router(audit.router)
