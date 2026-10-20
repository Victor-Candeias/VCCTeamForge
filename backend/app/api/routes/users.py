from fastapi import APIRouter, Depends, Response

from app.api.deps import get_current_user
from app.domain.users import User
from app.schemas.auth import CurrentUserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=CurrentUserResponse)
def get_me(response: Response, user: User = Depends(get_current_user)) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    return CurrentUserResponse.from_user(user)
