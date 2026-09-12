from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import DashboardLayout, User
from app.repositories.dashboard_layout_repository import dashboard_layout_repository
from app.schemas.dashboard_layout import DashboardLayoutCreate, DashboardLayoutUpdate

ALLOWED_WIDGET_IDS = {
    "w-kpis",
    "w-funnel",
    "w-revenue",
    "w-performers",
    "w-conversions",
    "w-activities",
    "w-deals",
    "w-ai",
}


class DashboardLayoutService:
    @staticmethod
    def org(user: User) -> str:
        value = effective_organization_id(user)
        if not value:
            raise NotFoundError(message="Organization not found")
        return value

    @staticmethod
    def validate_widgets(widgets: list[dict]) -> None:
        if any(
            not isinstance(widget, dict) or widget.get("id") not in ALLOWED_WIDGET_IDS
            for widget in widgets
        ):
            raise ConflictError(message="Dashboard contains an unsupported widget")

    async def list(self, db, user, page, limit):
        return await dashboard_layout_repository.list(
            db, self.org(user), user.id, (page - 1) * limit, limit
        )

    async def get(self, db, user, layout_id, mutate=False):
        item = await dashboard_layout_repository.get(
            db, self.org(user), user.id, layout_id, mutate=mutate
        )
        if not item:
            raise NotFoundError(message="Dashboard not found")
        return item

    async def create(self, db: AsyncSession, user: User, payload: DashboardLayoutCreate):
        self.validate_widgets(payload.widgets)
        item = DashboardLayout(
            organization_id=self.org(user), owner_id=user.id, **payload.model_dump()
        )
        db.add(item)
        try:
            await db.commit()
            await db.refresh(item)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="A dashboard with this name already exists") from exc
        return item

    async def update(self, db, user, layout_id, payload: DashboardLayoutUpdate):
        item = await self.get(db, user, layout_id, True)
        data = payload.model_dump(exclude_unset=True)
        if "widgets" in data:
            self.validate_widgets(data["widgets"])
        for key, value in data.items():
            setattr(item, key, value)
        try:
            await db.commit()
            await db.refresh(item)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="A dashboard with this name already exists") from exc
        return item

    async def delete(self, db, user, layout_id):
        item = await self.get(db, user, layout_id, True)
        await db.delete(item)
        await db.commit()


dashboard_layout_service = DashboardLayoutService()
