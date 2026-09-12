from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, update

from app.models import (
    Integration,
    IntegrationDelivery,
    Notification,
    Task,
    User,
    Workflow,
    WorkflowEvent,
    WorkflowRun,
)


class WorkflowRepository:
    async def list(self, db, organization_id, offset, limit):
        base = Workflow.organization_id == organization_id
        rows = (
            await db.scalars(
                select(Workflow)
                .where(base)
                .order_by(Workflow.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        total = int((await db.scalar(select(func.count()).select_from(Workflow).where(base))) or 0)
        return rows, total

    async def get(self, db, organization_id, workflow_id):
        return await db.scalar(
            select(Workflow).where(
                Workflow.id == workflow_id, Workflow.organization_id == organization_id
            )
        )

    async def runs(self, db, workflow_id, limit=50):
        return (
            await db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.workflow_id == workflow_id)
                .order_by(WorkflowRun.started_at.desc())
                .limit(limit)
            )
        ).all()

    async def active_for_event(self, db, event):
        return (
            await db.scalars(
                select(Workflow).where(
                    Workflow.organization_id == event.organization_id,
                    Workflow.module == event.module,
                    Workflow.trigger == event.trigger,
                    Workflow.is_active.is_(True),
                )
            )
        ).all()

    async def pending_events(self, db, limit=100):
        now = datetime.now(UTC)
        claimable = or_(
            and_(
                WorkflowEvent.status.in_(("Pending", "Retry")),
                or_(
                    WorkflowEvent.next_attempt_at.is_(None),
                    WorkflowEvent.next_attempt_at <= now,
                ),
            ),
            and_(
                WorkflowEvent.status == "Processing",
                WorkflowEvent.claimed_at < now - timedelta(minutes=15),
            ),
        )
        return (
            await db.scalars(
                select(WorkflowEvent)
                .where(claimable)
                .order_by(WorkflowEvent.created_at)
                .limit(limit)
            )
        ).all()

    async def claim_event(self, db, event_id: str):
        now = datetime.now(UTC)
        claimable = or_(
            and_(
                WorkflowEvent.status.in_(("Pending", "Retry")),
                or_(
                    WorkflowEvent.next_attempt_at.is_(None),
                    WorkflowEvent.next_attempt_at <= now,
                ),
            ),
            and_(
                WorkflowEvent.status == "Processing",
                WorkflowEvent.claimed_at < now - timedelta(minutes=15),
            ),
        )
        result = await db.execute(
            update(WorkflowEvent)
            .where(
                WorkflowEvent.id == event_id,
                claimable,
            )
            .values(
                status="Processing",
                claimed_at=now,
                attempts=WorkflowEvent.attempts + 1,
            )
            .returning(WorkflowEvent.id)
        )
        claimed = result.scalar_one_or_none()
        await db.commit()
        return await db.get(WorkflowEvent, claimed) if claimed else None

    async def retry_event(self, db, event_id: str, error: str) -> None:
        event = await db.get(WorkflowEvent, event_id)
        if not event:
            return
        event.status = "Failed" if event.attempts >= 5 else "Retry"
        event.next_attempt_at = (
            None
            if event.status == "Failed"
            else datetime.now(UTC) + timedelta(seconds=min(300, 2**event.attempts))
        )
        event.claimed_at = None
        event.last_error = error[:500]
        await db.commit()

    async def get_entity(self, db, model, entity_id: str):
        return await db.get(model, entity_id)

    async def active_user(self, db, organization_id: str, user_id: str):
        return await db.scalar(
            select(User).where(
                User.id == user_id,
                User._organization_id == organization_id,
                User.is_active.is_(True),
            )
        )

    async def connected_integration(self, db, organization_id: str, integration_id: str):
        return await db.scalar(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.organization_id == organization_id,
                Integration.is_connected.is_(True),
            )
        )

    async def enqueue_integration_delivery(
        self,
        db,
        *,
        integration: Integration,
        event: WorkflowEvent,
        workflow: Workflow,
        action_index: int,
        payload: dict,
    ) -> None:
        db.add(
            IntegrationDelivery(
                organization_id=event.organization_id,
                integration_id=integration.id,
                provider=integration.provider,
                event_name="workflow.action",
                payload=payload,
                idempotency_key=f"workflow:{event.id}:{workflow.id}:{action_index}",
            )
        )

    async def create_task(self, db, data: dict) -> None:
        db.add(Task(**data))

    async def create_notification(self, db, data: dict) -> None:
        db.add(Notification(**data))


workflow_repository = WorkflowRepository()
