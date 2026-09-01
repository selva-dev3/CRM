from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, CustomField, SLAPolicy, SystemSetting, User, Webhook


class SettingRepository:
    """DB query layer for system settings and related admin entities
    (audit logs, custom fields, webhooks, SLA policies). No business logic here.
    """

    async def get_by_key(self, db: AsyncSession, key: str) -> SystemSetting | None:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        return result.scalars().first()

    async def upsert(self, db: AsyncSession, *, key: str, value: str) -> None:
        setting = await self.get_by_key(db, key)
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))

    async def list_audit_logs(self, db: AsyncSession, *, page: int, limit: int) -> list[tuple]:
        result = await db.execute(
            select(AuditLog, User.name, User.email)
            .outerjoin(User, AuditLog.user_id == User.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [row._tuple() for row in result.all()]

    async def list_audit_logs_export(self, db: AsyncSession, limit: int = 500) -> list[tuple]:
        result = await db.execute(
            select(AuditLog, User.name, User.email)
            .outerjoin(User, AuditLog.user_id == User.id)
            .limit(limit)
        )
        return [row._tuple() for row in result.all()]

    async def list_custom_fields(
        self, db: AsyncSession, entity_type: str | None = None
    ) -> list[CustomField]:
        stmt = select(CustomField)
        if entity_type:
            stmt = stmt.where(CustomField.entity_type == entity_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_custom_field(self, db: AsyncSession, *, data: dict) -> CustomField:
        field = CustomField(**data)
        db.add(field)
        return field

    async def get_custom_field(self, db: AsyncSession, field_id: str) -> CustomField | None:
        result = await db.execute(select(CustomField).where(CustomField.id == field_id))
        return result.scalars().first()

    async def delete_custom_field(self, db: AsyncSession, field: CustomField) -> None:
        await db.delete(field)

    async def list_webhooks(
        self, db: AsyncSession, *, organization_id: str, limit: int = 20
    ) -> list[Webhook]:
        result = await db.execute(
            select(Webhook).where(Webhook.organization_id == organization_id).limit(limit)
        )
        return list(result.scalars().all())

    async def list_all_webhooks(self, db: AsyncSession, limit: int = 20) -> list[Webhook]:
        result = await db.execute(select(Webhook).limit(limit))
        return list(result.scalars().all())

    async def create_webhook(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        name: str,
        target_url: str,
        events: str,
    ) -> Webhook:
        webhook = Webhook(
            organization_id=organization_id,
            name=name,
            target_url=target_url,
            events=events,
        )
        db.add(webhook)
        return webhook

    async def get_webhook(self, db: AsyncSession, webhook_id: str) -> Webhook | None:
        result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
        return result.scalars().first()

    async def delete_webhook(self, db: AsyncSession, webhook: Webhook) -> None:
        await db.delete(webhook)

    async def list_sla(
        self, db: AsyncSession, *, organization_id: str, limit: int = 20
    ) -> list[SLAPolicy]:
        result = await db.execute(
            select(SLAPolicy).where(SLAPolicy.organization_id == organization_id).limit(limit)
        )
        return list(result.scalars().all())

    async def list_all_sla(self, db: AsyncSession, limit: int = 20) -> list[SLAPolicy]:
        result = await db.execute(select(SLAPolicy).limit(limit))
        return list(result.scalars().all())

    async def create_sla(self, db: AsyncSession, *, data: dict) -> SLAPolicy:
        sla = SLAPolicy(**data)
        db.add(sla)
        return sla

    async def get_user_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def list_table_names(self, db: AsyncSession) -> list[str]:
        result = await db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        )
        return [row[0] for row in result.all()]
