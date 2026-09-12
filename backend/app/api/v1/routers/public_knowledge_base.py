from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.schemas.support import PublicKnowledgeArticleResponse
from app.services.support_service import support_service

router = APIRouter()


@router.get("/{organization_slug}/{article_slug}", response_model=PublicKnowledgeArticleResponse)
async def public_article(
    organization_slug: str, article_slug: str, db: AsyncSession = Depends(get_db)
):
    article = await support_service.public_article(db, organization_slug, article_slug)
    if not article:
        raise NotFoundError(message="Knowledge article not found")
    return article
