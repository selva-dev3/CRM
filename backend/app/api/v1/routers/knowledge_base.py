from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.support import (
    KnowledgeArticleCreate,
    KnowledgeArticleResponse,
    KnowledgeArticleUpdate,
)
from app.services.support_service import support_service

router = APIRouter()


@router.get(
    "",
    response_model=list[KnowledgeArticleResponse],
    dependencies=[Depends(require_permission("knowledge_base:read"))],
)
async def list_articles(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    article_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await support_service.list_articles(db, user, search, article_status, page, limit)
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.post(
    "",
    response_model=KnowledgeArticleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("knowledge_base:create"))],
)
async def create_article(
    payload: KnowledgeArticleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.create_article(db, user, payload)


@router.get(
    "/{article_id}",
    response_model=KnowledgeArticleResponse,
    dependencies=[Depends(require_permission("knowledge_base:read"))],
)
async def get_article(
    article_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await support_service.article(db, user, article_id)


@router.patch(
    "/{article_id}",
    response_model=KnowledgeArticleResponse,
    dependencies=[Depends(require_permission("knowledge_base:update"))],
)
async def update_article(
    article_id: str,
    payload: KnowledgeArticleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.update_article(db, user, article_id, payload)


@router.post(
    "/{article_id}/publish",
    response_model=KnowledgeArticleResponse,
    dependencies=[Depends(require_permission("knowledge_base:publish"))],
)
async def publish_article(
    article_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await support_service.publish(db, user, article_id)


@router.delete(
    "/{article_id}",
    status_code=204,
    dependencies=[Depends(require_permission("knowledge_base:delete"))],
)
async def delete_article(
    article_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await support_service.delete_article(db, user, article_id)
    return Response(status_code=204)
