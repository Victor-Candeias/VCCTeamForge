from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Response, status
from pymongo.database import Database

from app.api.deps import get_db, require_permissions
from app.core.errors import NotFoundError
from app.domain.permissions import Permission
from app.domain.users import User
from app.schemas.common import Page, PageParams
from app.schemas.issue_search import IssueSearchQuery
from app.schemas.issues import Issue, IssueCreate, IssueSummary, IssueUpdate
from app.services.issues import IssueService

router = APIRouter(prefix="/issues", tags=["issues"])

can_read = require_permissions(Permission.ISSUES_READ)
can_write = require_permissions(Permission.ISSUES_WRITE)


def get_issue_service(db: Database = Depends(get_db)) -> IssueService:
    return IssueService(db)


def issue_object_id(issue_id: str) -> ObjectId:
    try:
        return ObjectId(issue_id)
    except (InvalidId, TypeError) as error:
        raise NotFoundError("Issue não encontrada") from error


@router.get("", response_model=Page[IssueSummary])
def list_issues(
    response: Response,
    query: IssueSearchQuery = Depends(IssueSearchQuery.from_query),
    page: PageParams = Depends(),
    user: User = Depends(can_read),
    service: IssueService = Depends(get_issue_service),
) -> Page[IssueSummary]:
    response.headers["Cache-Control"] = "no-store"
    items, total = service.search(user, query, page)
    return Page[IssueSummary](items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("", response_model=Issue, status_code=status.HTTP_201_CREATED)
def create_issue(
    data: IssueCreate,
    user: User = Depends(can_write),
    service: IssueService = Depends(get_issue_service),
) -> Issue:
    return service.create(user, data)


@router.get("/by-key/{key}", response_model=Issue)
def get_issue_by_key(
    key: str,
    response: Response,
    user: User = Depends(can_read),
    service: IssueService = Depends(get_issue_service),
) -> Issue:
    response.headers["Cache-Control"] = "no-store"
    issue, project = service.get_accessible_by_key(user, key)
    return service.to_issue(user, issue, project)


@router.get("/{issue_id}", response_model=Issue)
def get_issue(
    issue_id: str,
    response: Response,
    user: User = Depends(can_read),
    service: IssueService = Depends(get_issue_service),
) -> Issue:
    response.headers["Cache-Control"] = "no-store"
    issue, project = service.get_accessible(user, issue_object_id(issue_id))
    return service.to_issue(user, issue, project)


@router.patch("/{issue_id}", response_model=Issue)
def update_issue(
    issue_id: str,
    data: IssueUpdate,
    user: User = Depends(can_write),
    service: IssueService = Depends(get_issue_service),
) -> Issue:
    return service.update(user, issue_object_id(issue_id), data)
