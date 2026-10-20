from fastapi import APIRouter, Depends

from app.api.deps import verify_csrf
from app.api.routes import auth, health, users

api_router = APIRouter(dependencies=[Depends(verify_csrf)])
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
