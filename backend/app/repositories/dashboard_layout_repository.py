from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DashboardLayout


class DashboardLayoutRepository:
    async def list(
        self, db: AsyncSession, organization_id: str, user_id: str, offset: int, limit: int
    ):
        visible = or_(DashboardLayout.owner_id == user_id, DashboardLayout.is_shared.is_(True))
        base = DashboardLayout.organization_id == organization_id
        rows = (
            await db.scalars(
                select(DashboardLayout)
                .where(base, visible)
                .order_by(DashboardLayout.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        total = int(
            (
                await db.scalar(
                    select(func.count()).select_from(DashboardLayout).where(base, visible)
                )
            )
            or 0
        )
        return rows, total

    async def get(
        self,
        db: AsyncSession,
        organization_id: str,
        user_id: str,
        layout_id: str,
        *,
        mutate: bool = False,
    ):
        filters = [
            DashboardLayout.id == layout_id,
            DashboardLayout.organization_id == organization_id,
        ]
        filters.append(
            DashboardLayout.owner_id == user_id
            if mutate
            else or_(DashboardLayout.owner_id == user_id, DashboardLayout.is_shared.is_(True))
        )
        return await db.scalar(select(DashboardLayout).where(*filters))


dashboard_layout_repository = DashboardLayoutRepository()
