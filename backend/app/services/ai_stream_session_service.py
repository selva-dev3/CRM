from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.db.session import AsyncSessionLocal
from app.models import ApiKey, Organization, User, UserSession


class AIStreamSessionService:
    """Revalidate the authenticated principal without sharing the request DB session."""

    async def is_current(
        self,
        *,
        user_id: str,
        organization_id: str,
        session_id: str | None,
        api_key_id: str | None,
    ) -> bool:
        now = datetime.now(UTC)
        async with AsyncSessionLocal() as db:
            user = await db.get(User, user_id)
            organization = await db.get(Organization, organization_id)
            if (
                user is None
                or not user.is_active
                or organization is None
                or not organization.is_active
                or organization.status != "active"
            ):
                return False
            if api_key_id:
                api_key = await db.scalar(
                    select(ApiKey).where(
                        ApiKey.id == api_key_id,
                        ApiKey.created_by == user_id,
                        ApiKey.organization_id == organization_id,
                    )
                )
                return bool(
                    api_key
                    and api_key.is_active
                    and (api_key.expires_at is None or api_key.expires_at > now)
                )
            if not session_id:
                return False
            session = await db.get(UserSession, session_id)
            return bool(
                session
                and session.user_id == user_id
                and session.is_current
                and session.revoked_at is None
                and (session.expires_at is None or session.expires_at > now)
            )

    async def assert_current_for_update(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        organization_id: str,
        session_id: str | None,
        api_key_id: str | None,
    ) -> None:
        """Lock and verify stream ownership in the transaction that persists results."""
        now = datetime.now(UTC)
        user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
        organization = await db.scalar(
            select(Organization)
            .where(Organization.id == organization_id)
            .with_for_update()
        )
        valid = bool(
            user
            and user.is_active
            and organization
            and organization.is_active
            and organization.status == "active"
        )
        if valid and api_key_id:
            api_key = await db.scalar(
                select(ApiKey)
                .where(
                    ApiKey.id == api_key_id,
                    ApiKey.created_by == user_id,
                    ApiKey.organization_id == organization_id,
                )
                .with_for_update()
            )
            valid = bool(
                api_key
                and api_key.is_active
                and (api_key.expires_at is None or api_key.expires_at > now)
            )
        elif valid and session_id:
            session = await db.scalar(
                select(UserSession).where(UserSession.id == session_id).with_for_update()
            )
            valid = bool(
                session
                and session.user_id == user_id
                and session.is_current
                and session.revoked_at is None
                and (session.expires_at is None or session.expires_at > now)
            )
        else:
            valid = False
        if not valid:
            raise APIException(
                status_code=409,
                code="AI_STREAM_SESSION_REPLACED",
                message="This AI stream no longer belongs to the active session.",
            )


ai_stream_session_service = AIStreamSessionService()
