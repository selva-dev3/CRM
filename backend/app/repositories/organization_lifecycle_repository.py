"""Persistence for platform provisioning and the reviewed tenant deletion graph."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models import (
    AuditLog,
    Organization,
    OrganizationDeletion,
    OrganizationFileCleanup,
    OrganizationInvitation,
    OrganizationSubscription,
    Permission,
    Role,
    User,
    UserInvitation,
)

# Indirect ownership is explicit: never infer tenant ownership through an arbitrary FK.
INDIRECT_OWNERS = {
    "ai_prompts": ("conversation_id", "ai_conversations"),
    "ai_lead_scores": ("lead_id", "leads"),
    "ai_meeting_summaries": ("meeting_id", "meetings"),
    **dict.fromkeys(
        (
            "user_profiles",
            "user_sessions",
            "refresh_tokens",
            "magic_link_tokens",
            "password_resets",
            "email_verifications",
            "otp_verifications",
            "calendar_events",
            "user_roles",
        ),
        ("user_id", "users"),
    ),
    "role_permissions": ("role_id", "roles"),
    "company_contacts": ("company_id", "companies"),
    "contact_addresses": ("contact_id", "contacts"),
    "contact_tags": ("contact_id", "contacts"),
    "deal_activities": ("deal_id", "deals"),
    "deal_products": ("deal_id", "deals"),
    "document_versions": ("document_id", "documents"),
    "email_logs": ("email_id", "emails"),
    "invoice_items": ("invoice_id", "invoices"),
    **dict.fromkeys(
        ("lead_scores", "lead_tags", "lead_activities", "lead_notes", "lead_attachments"),
        ("lead_id", "leads"),
    ),
    "meeting_attendees": ("meeting_id", "meetings"),
    "quote_items": ("quote_id", "quotes"),
    "task_comments": ("task_id", "tasks"),
    "task_attachments": ("task_id", "tasks"),
}
PLATFORM_TABLES = {"organization_deletions", "organization_file_cleanups"}
STORAGE_COLUMNS = {
    "organizations": {"logo_url": "url"},
    "organization_settings": {"logo_url": "url"},
    "documents": {"s3_key": "key", "file_url": "url"},
    "document_versions": {"file_url": "url"},
    "lead_attachments": {"file_url": "url"},
    "task_attachments": {"file_url": "url"},
    "user_profiles": {"avatar_url": "url"},
    "quotes": {"pdf_s3_key": "key"},
    "invoices": {"pdf_s3_key": "key"},
    "payments": {"receipt_s3_key": "key"},
    "report_exports": {"s3_key": "key", "download_url": "url"},
    "whatsapp_messages": {"media_s3_key": "key"},
    # Unscoped upload records are never guessed to belong to a tenant.
    "file_uploads": {"file_path": "url"},
}


def tenant_predicates(organization_id: str) -> dict[str, ColumnElement[bool]]:
    tables = Base.metadata.tables
    predicates = {
        name: table.c.organization_id == organization_id
        for name, table in tables.items()
        if "organization_id" in table.c and name not in PLATFORM_TABLES
    }
    predicates["organizations"] = tables["organizations"].c.id == organization_id
    for name, (column, parent) in INDIRECT_OWNERS.items():
        predicates[name] = (
            tables[name].c[column].in_(select(tables[parent].c.id).where(predicates[parent]))
        )
    return predicates


class OrganizationLifecycleRepository:
    async def resolve_invitation_role(
        self, db: AsyncSession, role_value: str, organization_id: str | None
    ) -> Role | None:
        normalized = role_value.strip()
        if organization_id:
            local = await db.scalar(
                select(Role)
                .where(
                    Role.organization_id == organization_id,
                    or_(
                        Role.id == normalized,
                        func.lower(func.btrim(Role.name)) == normalized.lower(),
                    ),
                )
                .limit(1)
                .with_for_update()
            )
            if local:
                return local
        legacy = await db.scalar(
            select(Role)
            .where(
                Role.organization_id.is_(None),
                or_(
                    Role.id == normalized,
                    func.lower(func.btrim(Role.name)) == normalized.lower(),
                ),
            )
            .limit(1)
            .with_for_update()
        )
        if legacy and organization_id:
            return await db.scalar(
                select(Role)
                .where(
                    Role.organization_id == organization_id,
                    func.lower(func.btrim(Role.name)) == legacy.name.strip().lower(),
                )
                .limit(1)
                .with_for_update()
            )
        return legacy if organization_id is None else None

    async def role_names(self, db: AsyncSession, ids: list[str]) -> dict[str, str]:
        if not ids:
            return {}
        rows = await db.execute(select(Role.id, Role.name).where(Role.id.in_(ids)))
        return {identifier: name for identifier, name in rows}  # noqa: C416

    async def lock_invitation_for_acceptance(
        self, db: AsyncSession, token: str
    ) -> OrganizationInvitation | None:
        invitation = await db.scalar(
            select(OrganizationInvitation).where(OrganizationInvitation.token == token).limit(1)
        )
        if invitation is None:
            return None
        await self.lock_invitation_email(db, invitation.email.strip().lower())
        await db.scalar(
            select(Organization.id)
            .where(Organization.id == invitation.organization_id)
            .with_for_update()
        )
        return await db.scalar(
            select(OrganizationInvitation)
            .where(OrganizationInvitation.token == token)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def lock_invitation_organization(
        self, db: AsyncSession, organization_id: str
    ) -> Organization | None:
        return await db.scalar(
            select(Organization)
            .where(Organization.id == organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def lock_invitation_for_management(
        self, db: AsyncSession, invitation_id: str, organization_id: str
    ) -> OrganizationInvitation | None:
        conditions = (
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == organization_id,
        )
        invitation = await db.scalar(select(OrganizationInvitation).where(*conditions))
        if invitation is None:
            return None
        await self.lock_invitation_email(db, invitation.email.strip().lower())
        await self.lock_invitation_organization(db, organization_id)
        return await db.scalar(
            select(OrganizationInvitation)
            .where(*conditions)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def tenant_member_count(self, db: AsyncSession, organization_id: str) -> int:
        return int(
            await db.scalar(
                select(func.count())
                .select_from(User)
                .where(User._organization_id == organization_id)
            )
            or 0
        )

    async def subscription_for_membership(
        self, db: AsyncSession, organization_id: str
    ) -> OrganizationSubscription | None:
        return await db.scalar(select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == organization_id
        ).with_for_update())

    async def pending_legacy_invitation_exists(self, db: AsyncSession, email: str) -> bool:
        return bool(await db.scalar(select(UserInvitation.id).where(
            func.lower(func.btrim(UserInvitation.email)) == email,
            func.lower(UserInvitation.status) == "pending",
            UserInvitation.created_at > datetime.now(UTC) - timedelta(hours=24),
        ).limit(1)))

    async def set_lock_timeout(self, db: AsyncSession) -> None:
        await db.execute(text("SET LOCAL lock_timeout = '3s'"))

    async def lock_invitation_email(self, db: AsyncSession, email: str) -> None:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:email, 482109))"), {"email": email}
        )

    async def permission_catalog(self, db: AsyncSession) -> dict[str, str]:
        return {  # noqa: C416 - destructure SQLAlchemy Row for static typing
            key: identifier
            for key, identifier in await db.execute(select(Permission.key, Permission.id))
        }

    async def email_in_use(self, db: AsyncSession, email: str) -> bool:
        return bool(
            await db.scalar(select(User.id).where(func.lower(func.btrim(User.email)) == email))
        )

    async def pending_invitation_exists(self, db: AsyncSession, email: str) -> bool:
        return bool(
            await db.scalar(
                select(OrganizationInvitation.id)
                .where(
                    func.lower(func.btrim(OrganizationInvitation.email)) == email,
                    OrganizationInvitation.status == "Pending",
                    OrganizationInvitation.expires_at > datetime.now(UTC),
                )
                .limit(1)
            )
        )

    async def pending_invitation_in_other_organization(
        self, db: AsyncSession, email: str, organization_id: str
    ) -> bool:
        return bool(
            await db.scalar(
                select(OrganizationInvitation.id)
                .where(
                    func.lower(func.btrim(OrganizationInvitation.email)) == email,
                    OrganizationInvitation.status == "Pending",
                    OrganizationInvitation.expires_at > datetime.now(UTC),
                    OrganizationInvitation.organization_id.is_distinct_from(organization_id),
                )
                .limit(1)
            )
        )

    async def pending_invitation_for_organization(
        self, db: AsyncSession, email: str, organization_id: str
    ) -> OrganizationInvitation | None:
        return await db.scalar(
            select(OrganizationInvitation)
            .where(
                func.lower(func.btrim(OrganizationInvitation.email)) == email,
                OrganizationInvitation.status == "Pending",
                OrganizationInvitation.organization_id == organization_id,
            )
            .order_by(OrganizationInvitation.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    async def create_invitation(self, db: AsyncSession, **data) -> OrganizationInvitation:
        invitation = OrganizationInvitation(**data)
        db.add(invitation)
        return invitation

    async def audit(self, db: AsyncSession, *, actor_id: str, action: str, details: str) -> None:
        db.add(AuditLog(user_id=actor_id, organization_id=None, action=action, details=details))

    async def lock_tenant_records(self, db: AsyncSession, organization_id: str) -> None:
        # Parent lock prevents new direct tenant references. Row locks also prevent
        # workers claiming owned work and FK inserts into indirect child records.
        await db.execute(text("SET LOCAL lock_timeout = '3s'"))
        predicates = tenant_predicates(organization_id)
        for name in sorted(predicates):
            table = Base.metadata.tables[name]
            column = next(iter(table.primary_key.columns))
            rows = await db.stream_scalars(
                select(column).where(predicates[name]).order_by(column).with_for_update()
            )
            async for _ in rows:
                pass

    async def cross_tenant_reference(self, db: AsyncSession, organization_id: str) -> bool:
        predicates = tenant_predicates(organization_id)
        for table in Base.metadata.tables.values():
            if table.name in PLATFORM_TABLES:
                continue
            for fk in table.foreign_keys:
                parent = fk.column.table
                if parent.name not in predicates or parent.name == "organizations":
                    continue
                target = select(fk.column).where(predicates[parent.name])
                query = select(fk.parent).where(fk.parent.in_(target))
                if table.name in predicates:
                    query = query.where(predicates[table.name].is_not(True))
                if await db.scalar(select(query.exists())):
                    return True
        return False

    async def protected_platform_member(self, db: AsyncSession, organization_id: str) -> bool:
        return bool(
            await db.scalar(
                select(User.id)
                .where(
                    User._organization_id == organization_id,
                    User.is_platform_admin.is_(True),
                )
                .limit(1)
            )
        )

    async def billing_blocked(self, db: AsyncSession, organization_id: str) -> bool:
        payments = Base.metadata.tables["payments"]
        if await db.scalar(
            select(payments.c.id).where(payments.c.organization_id == organization_id).limit(1)
        ):
            return True
        subscription = await db.scalar(
            select(OrganizationSubscription)
            .where(OrganizationSubscription.organization_id == organization_id)
            .execution_options(populate_existing=True)
        )
        return bool(
            subscription
            and (
                subscription.customer_id
                or subscription.payment_provider
                or subscription.checkout_operation_id
                or subscription.checkout_expires_at
                or subscription.invoice_id
                or subscription.subscription_id
                or subscription.checkout_session_id
                or subscription.reconciliation_required
                or subscription.legacy_provider_data
                or (subscription.amount or 0) > 0
            )
        )

    async def has_active_work(self, db: AsyncSession, organization_id: str) -> bool:
        predicates = tenant_predicates(organization_id)
        for name, column, states in (
            ("whatsapp_messages", "status", ("PENDING", "PROCESSING", "UNKNOWN")),
            ("whatsapp_messages", "work_status", ("PENDING", "PROCESSING")),
            ("whatsapp_webhook_events", "status", ("PENDING",)),
            ("emails", "status", ("Processing", "Unknown")),
            ("integration_deliveries", "status", ("Processing",)),
            ("quotes", "delivery_status", ("processing", "sending", "unknown")),
            ("quote_delivery_attempts", "delivery_status", ("processing", "sending", "unknown")),
            ("invoices", "delivery_status", ("processing", "sending", "unknown")),
            ("ai_runs", "status", ("started", "running", "pending", "awaiting_confirmation")),
            ("ai_actions", "status", ("executing",)),
        ):
            table = Base.metadata.tables[name]
            if await db.scalar(
                select(table.c.id)
                .where(
                    predicates[name], func.lower(table.c[column]).in_([s.lower() for s in states])
                )
                .limit(1)
            ):
                return True
        scheduled = Base.metadata.tables["scheduled_reports"]
        return bool(
            await db.scalar(
                select(scheduled.c.id)
                .where(predicates["scheduled_reports"], scheduled.c.claimed_until.is_not(None))
                .limit(1)
            )
        )

    async def storage_references(
        self, db: AsyncSession, organization_id: str, *, owned_only: bool | None = None
    ) -> AsyncIterator[tuple[bool, str, str]]:
        predicates = tenant_predicates(organization_id)
        for name, columns in STORAGE_COLUMNS.items():
            table = Base.metadata.tables[name]
            owned = predicates.get(name)
            for column, kind in columns.items():
                query = select(
                    table.c[column], owned if owned is not None else text("false")
                ).where(table.c[column].is_not(None), table.c[column] != "")
                if owned_only is True:
                    if owned is None:
                        continue
                    query = query.where(owned)
                elif owned_only is False and owned is not None:
                    query = query.where(owned.is_not(True))
                rows = await db.stream(query)
                async for value, is_owned in rows:
                    yield bool(is_owned), value, kind

    async def storage_prefix_owners(
        self, db: AsyncSession, organization_id: str
    ) -> AsyncIterator[tuple[str, str]]:
        yield "organization", organization_id
        for name, kind in (("users", "user"), ("leads", "lead"), ("scheduled_reports", "schedule")):
            table = Base.metadata.tables[name]
            rows = await db.stream_scalars(
                select(table.c.id).where(table.c.organization_id == organization_id)
            )
            async for identifier in rows:
                yield kind, identifier

    async def storage_prefix_conflict(
        self, db: AsyncSession, organization_id: str, prefixes: list[str]
    ) -> bool:
        # Return only an existence result, never transfer all platform owners.
        # starts_with has no wildcard semantics, including for legacy string IDs.
        for name in ("organizations", "users", "leads", "scheduled_reports"):
            table = Base.metadata.tables[name]
            identifier = table.c.id
            owned = (
                identifier == organization_id
                if name == "organizations"
                else table.c.organization_id == organization_id
            )
            safe_org = func.left(func.regexp_replace(identifier, "[^A-Za-z0-9_-]", "_", "g"), 64)
            expressions = {
                "organizations": [
                    "documents/" + safe_org + "/",
                    "exports/" + safe_org + "/",
                    "branding/" + identifier + "_",
                    identifier + "/quotes/",
                    identifier + "/invoices/",
                    identifier + "/receipts/",
                ],
                "users": ["avatars/" + identifier + "_"],
                "leads": ["leads/" + identifier + "/"],
                "scheduled_reports": ["exports/scheduled/" + identifier + "/"],
            }[name]
            overlaps = [
                or_(func.starts_with(expression, prefix), func.starts_with(prefix, expression))
                for expression in expressions
                for prefix in prefixes
            ]
            if await db.scalar(
                select(identifier).where(owned.is_not(True), or_(*overlaps)).limit(1)
            ):
                return True
        return False

    async def create_deletion(
        self, db: AsyncSession, *, organization: Organization, actor_id: str
    ) -> OrganizationDeletion:
        operation = OrganizationDeletion(
            organization_id=organization.id, organization_name=organization.name, actor_id=actor_id
        )
        db.add(operation)
        await db.flush()
        return operation

    async def enqueue_files(
        self, db: AsyncSession, operation_id: str, keys: set[str], *, endpoint: str, bucket: str
    ) -> None:
        db.add_all(
            [
                OrganizationFileCleanup(
                    operation_id=operation_id, object_key=key, endpoint=endpoint, bucket=bucket
                )
                for key in sorted(keys)
            ]
        )

    async def delete_dependencies(self, db: AsyncSession, organization_id: str) -> None:
        predicates = tenant_predicates(organization_id)
        # UserRole intentionally restricts ordinary role deletion. Remove tenant
        # mappings explicitly inside the organization-deletion transaction before
        # the organization cascades through users and roles.
        user_roles = Base.metadata.tables["user_roles"]
        await db.execute(delete(user_roles).where(predicates["user_roles"]))
        for name in ("leads", "quotes", "deal_products"):
            await db.execute(delete(Base.metadata.tables[name]).where(predicates[name]))
        settings = Base.metadata.tables["settings"]
        await db.execute(
            delete(settings).where(
                settings.c.key.in_(
                    [
                        f"default_registration_role:{organization_id}",
                        f"default_registration_roles:{organization_id}",
                    ]
                )
            )
        )

    async def get_deletion(
        self, db: AsyncSession, operation_id: str
    ) -> OrganizationDeletion | None:
        return await db.get(OrganizationDeletion, operation_id)

    async def cleanup_counts(self, db: AsyncSession, operation_id: str) -> dict[str, int]:
        return {  # noqa: C416 - destructure SQLAlchemy Row for static typing
            status: count
            for status, count in await db.execute(
                select(OrganizationFileCleanup.status, func.count())
                .where(OrganizationFileCleanup.operation_id == operation_id)
                .group_by(OrganizationFileCleanup.status)
            )
        }

    async def retry_cleanup(self, db: AsyncSession, operation_id: str) -> None:
        await db.execute(
            update(OrganizationFileCleanup)
            .where(
                OrganizationFileCleanup.operation_id == operation_id,
                OrganizationFileCleanup.status == "failed",
            )
            .values(
                status="pending", attempts=0, error_code=None, next_attempt_at=datetime.now(UTC)
            )
        )

    async def claim_file(self, db: AsyncSession) -> OrganizationFileCleanup | None:
        now = datetime.now(UTC)
        item = await db.scalar(
            select(OrganizationFileCleanup)
            .where(
                OrganizationFileCleanup.status == "pending",
                OrganizationFileCleanup.next_attempt_at <= now,
                or_(
                    OrganizationFileCleanup.claimed_until.is_(None),
                    OrganizationFileCleanup.claimed_until < now,
                ),
            )
            .order_by(OrganizationFileCleanup.next_attempt_at, OrganizationFileCleanup.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if item:
            item.claimed_until = now + timedelta(minutes=5)
            item.attempts += 1
        return item

    async def renew_file_claim(self, db: AsyncSession, item: OrganizationFileCleanup) -> bool:
        deadline = datetime.now(UTC) + timedelta(minutes=5)
        result = await db.execute(
            update(OrganizationFileCleanup)
            .where(
                OrganizationFileCleanup.id == item.id,
                OrganizationFileCleanup.status == "pending",
                OrganizationFileCleanup.claimed_until == item.claimed_until,
            )
            .values(claimed_until=deadline)
            .returning(OrganizationFileCleanup.id)
        )
        if result.scalar_one_or_none() is None:
            return False
        item.claimed_until = deadline
        return True

    async def finish_file(
        self, db: AsyncSession, item: OrganizationFileCleanup, error: str | None
    ) -> None:
        await db.execute(
            update(OrganizationFileCleanup)
            .where(
                OrganizationFileCleanup.id == item.id,
                OrganizationFileCleanup.claimed_until == item.claimed_until,
            )
            .values(
                status="complete" if not error else "failed" if item.attempts >= 5 else "pending",
                claimed_until=None,
                error_code=error,
                next_attempt_at=datetime.now(UTC)
                + timedelta(seconds=min(3600, 30 * 2**item.attempts)),
            )
        )
