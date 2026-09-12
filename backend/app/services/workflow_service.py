from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import Deal, Lead, Project, Task, Ticket, User, Workflow, WorkflowEvent, WorkflowRun
from app.repositories.workflow_repository import workflow_repository
from app.schemas.crm_schemas import DealUpdate, LeadUpdate, TaskUpdate
from app.schemas.project import ProjectUpdate
from app.schemas.support import TicketUpdate
from app.services.auth_service import AuthService
from app.services.record_access_service import record_access_service

ENTITY_MODELS = {
    "leads": Lead,
    "deals": Deal,
    "tasks": Task,
    "projects": Project,
    "tickets": Ticket,
}
EDITABLE_FIELDS = {
    "leads": {"status", "score"},
    "deals": {"stage", "probability"},
    "tasks": {"status", "priority"},
    "projects": {"status", "priority", "completion_percentage"},
    "tickets": {"status", "priority"},
}
UPDATE_SCHEMAS = {
    "leads": LeadUpdate,
    "deals": DealUpdate,
    "tasks": TaskUpdate,
    "projects": ProjectUpdate,
    "tickets": TicketUpdate,
}
ACTION_PERMISSIONS = {
    "assign": None,
    "update_field": None,
    "create_task": "tasks:create",
    "notification": "notifications:send",
    "email": "emails:send",
    "webhook": "integrations:manage",
}


class WorkflowService:
    @staticmethod
    def org(user: User) -> str:
        value = effective_organization_id(user)
        if not value:
            raise NotFoundError(message="Organization not found")
        return value

    async def _validate(self, db, user, module, actions):
        permissions = set(await AuthService().get_user_permissions(db, user))
        for action in actions:
            kind = action.get("type")
            required = ACTION_PERMISSIONS.get(kind)
            if kind not in ACTION_PERMISSIONS:
                raise ConflictError(message=f"Unsupported workflow action: {kind}")
            if kind == "update_field" and action.get("field") not in EDITABLE_FIELDS[module]:
                raise ConflictError(message="Workflow field is not editable")
            if kind == "update_field":
                required = f"{module}:update"
                if action.get("value") is None:
                    raise ConflictError(message="Workflow field value cannot be null")
                try:
                    UPDATE_SCHEMAS[module](**{action["field"]: action.get("value")})
                except ValidationError as exc:
                    raise ConflictError(message="Workflow field value is invalid") from exc
            if kind == "assign" and not action.get("user_id"):
                raise ConflictError(message="Assignment actions require a user")
            if kind == "email" and not str(action.get("to_email", "")).strip():
                raise ConflictError(message="Email actions require a recipient")
            if kind == "webhook" and not action.get("integration_id"):
                raise ConflictError(message="Webhook actions require a connected integration")
            if kind == "create_task":
                try:
                    due_days = int(action.get("due_days", 1))
                except (TypeError, ValueError) as exc:
                    raise ConflictError(message="Task due days must be an integer") from exc
                if due_days < 0 or due_days > 3650:
                    raise ConflictError(message="Task due days must be between 0 and 3650")
            if kind == "assign":
                required = (
                    f"{module}:assign"
                    if module in {"leads", "deals", "tasks", "projects", "tickets"}
                    else None
                )
            if required and required not in permissions:
                raise ForbiddenError(
                    message=f"Missing permission required by workflow action: {required}"
                )

    @staticmethod
    def _record_is_accessible(access, entity) -> bool:
        return record_access_service.allows(
            access,
            assigned_to=getattr(entity, "assigned_to", None)
            or getattr(entity, "owner_id", None),
            created_by=getattr(entity, "created_by", None),
            team_id=getattr(entity, "team_id", None),
        )

    async def _update_field(self, db, actor, event, entity, action) -> None:
        field = action["field"]
        value = action.get("value")
        # These transitions carry business invariants and audit side effects.
        if event.module == "leads" and field == "status":
            from app.services.lead_service import lead_service

            await lead_service.update_lead(
                db,
                entity.id,
                LeadUpdate(status=value),
                actor,
                emit_workflow=False,
            )
            return
        if event.module == "deals" and field == "stage":
            from app.services.deal_service import deal_service

            await deal_service.update_deal_stage(
                db,
                entity.id,
                value,
                organization_id=event.organization_id,
                actor_id=actor.id,
            )
            return
        if event.module == "tickets" and field == "status":
            from app.services.support_service import support_service

            await support_service.update_ticket(
                db,
                actor,
                entity.id,
                TicketUpdate(status=value),
                emit_workflow=False,
            )
            return
        # Validation is repeated at execution in case a stored workflow predates
        # the current schema constraints.
        validated = UPDATE_SCHEMAS[event.module](**{field: value})
        setattr(entity, field, getattr(validated, field))

    async def list(self, db, user, page, limit):
        return await workflow_repository.list(db, self.org(user), (page - 1) * limit, limit)

    async def get(self, db, user, workflow_id):
        item = await workflow_repository.get(db, self.org(user), workflow_id)
        if not item:
            raise NotFoundError(message="Workflow not found")
        return item

    async def create(self, db, user, payload):
        data = payload.model_dump()
        await self._validate(db, user, payload.module, data["actions"])
        item = Workflow(
            organization_id=self.org(user),
            created_by=user.id,
            activated_by=user.id if payload.is_active else None,
            **data,
        )
        db.add(item)
        try:
            await db.commit()
            await db.refresh(item)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="A workflow with this name already exists") from exc
        return item

    async def update(self, db, user, workflow_id, payload):
        item = await self.get(db, user, workflow_id)
        data = payload.model_dump(exclude_unset=True)
        await self._validate(db, user, item.module, data.get("actions", item.actions))
        definition_changed = bool({"trigger", "conditions", "actions"} & data.keys())
        for key, value in data.items():
            setattr(item, key, value)
        if item.is_active and (data.get("is_active") is True or definition_changed):
            item.activated_by = user.id
        elif not item.is_active:
            item.activated_by = None
        await db.commit()
        await db.refresh(item)
        return item

    async def delete(self, db, user, workflow_id):
        item = await self.get(db, user, workflow_id)
        await db.delete(item)
        await db.commit()

    async def runs(self, db, user, workflow_id):
        await self.get(db, user, workflow_id)
        return await workflow_repository.runs(db, workflow_id)

    async def emit(
        self,
        db,
        *,
        organization_id,
        module,
        trigger,
        entity_id,
        actor_id,
        payload,
        correlation_id=None,
        depth=0,
    ):
        if depth > 5:
            return
        db.add(
            WorkflowEvent(
                organization_id=organization_id,
                module=module,
                trigger=trigger,
                entity_id=entity_id,
                actor_id=actor_id,
                correlation_id=correlation_id or str(uuid.uuid4()),
                depth=depth,
                payload=payload,
            )
        )

    @staticmethod
    def matches(conditions, payload):
        for condition in conditions:
            actual = payload.get(condition.get("field"))
            expected = condition.get("value")
            operator = condition.get("operator", "equals")
            if operator == "equals" and actual != expected:
                return False
            if operator == "not_equals" and actual == expected:
                return False
            if operator == "changed" and condition.get("field") not in payload.get(
                "changed_fields", []
            ):
                return False
        return True

    async def process_event(self, db, event):
        event_id = event.id
        workflows = await workflow_repository.active_for_event(db, event)
        for workflow in workflows:
            workflow_id = workflow.id
            if not self.matches(workflow.conditions, event.payload):
                continue
            existing_run = await db.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.event_id == event.id,
                    WorkflowRun.workflow_id == workflow.id,
                )
            )
            if existing_run and existing_run.status == "Completed":
                continue
            actor = (
                await workflow_repository.active_user(
                    db, event.organization_id, workflow.activated_by
                )
                if workflow.activated_by
                else None
            )
            if not actor:
                await self._record_failed_run(
                    db, event_id, workflow_id, existing_run, "WorkflowActivatorUnavailable"
                )
                continue
            try:
                await self._validate(db, actor, event.module, workflow.actions)
            except (ForbiddenError, ConflictError):
                await self._record_failed_run(
                    db, event_id, workflow_id, existing_run, "WorkflowAuthorizationFailed"
                )
                continue
            run = WorkflowRun(
                event_id=event.id,
                workflow_id=workflow.id,
                status="Running",
                action_results=[],
            )
            if existing_run:
                run = existing_run
                run.status = "Running"
                run.error = None
                run.finished_at = None
            else:
                db.add(run)
            await db.commit()
            run_id = run.id
            results: list[dict] = list(run.action_results or [])
            try:
                entity = await workflow_repository.get_entity(
                    db, ENTITY_MODELS[event.module], event.entity_id
                )
                if not entity or entity.organization_id != event.organization_id:
                    raise NotFoundError(message="Workflow record not found")
                access = await record_access_service.resolve(db, actor, event.module)
                if not self._record_is_accessible(access, entity):
                    raise NotFoundError(message="Workflow record not found")
                completed_indexes = {
                    result.get("action_index")
                    for result in results
                    if result.get("status") in {"completed", "queued"}
                }
                for action_index, action in enumerate(workflow.actions):
                    if action_index in completed_indexes:
                        continue
                    kind = action["type"]
                    result_status = "completed"
                    if kind == "assign":
                        assignee = await workflow_repository.active_user(
                            db, event.organization_id, action["user_id"]
                        )
                        if not assignee:
                            raise NotFoundError(message="Workflow assignee not found")
                        setattr(
                            entity,
                            "assigned_to" if hasattr(entity, "assigned_to") else "owner_id",
                            assignee.id,
                        )
                    elif kind == "update_field":
                        await self._update_field(db, actor, event, entity, action)
                    elif kind == "create_task":
                        assigned_to = action.get("assigned_to") or event.actor_id or actor.id
                        assignee = await workflow_repository.active_user(
                            db, event.organization_id, assigned_to
                        )
                        if not assignee:
                            raise NotFoundError(message="Workflow task assignee not found")
                        relation = (
                            {f"{event.module[:-1]}_id": event.entity_id}
                            if event.module in {"leads", "deals", "projects", "tickets"}
                            else {}
                        )
                        await workflow_repository.create_task(
                            db,
                            {
                                "organization_id": event.organization_id,
                                "title": action.get("title", "Workflow follow-up"),
                                "description": action.get("description"),
                                "priority": action.get("priority", "Medium"),
                                "status": "Pending",
                                "due_date": datetime.now(UTC)
                                + timedelta(days=int(action.get("due_days", 1))),
                                "assigned_to": assignee.id,
                                "created_by": actor.id,
                                **relation,
                            },
                        )
                    elif kind == "notification":
                        recipient_id = action.get("user_id") or event.actor_id or actor.id
                        recipient = await workflow_repository.active_user(
                            db, event.organization_id, recipient_id
                        )
                        if not recipient:
                            raise NotFoundError(message="Workflow notification recipient not found")
                        await workflow_repository.create_notification(
                            db,
                            {
                                "user_id": recipient.id,
                                "organization_id": event.organization_id,
                                "event_name": "workflow.action",
                                "entity_type": event.module[:-1],
                                "entity_id": event.entity_id,
                                "title": action.get("title", "Workflow notification"),
                                "message": action.get("message", workflow.name),
                                "payload": json.dumps({"workflow_id": workflow.id}),
                            },
                        )
                    elif kind == "email":
                        from app.services.email_domain_service import email_domain_service

                        await email_domain_service.queue_email(
                            db,
                            organization_id=event.organization_id,
                            to_email=action["to_email"],
                            subject=action.get("subject", workflow.name),
                            body=action.get("body", workflow.description or workflow.name),
                            idempotency_key=(f"workflow:{event.id}:{workflow.id}:{action_index}"),
                        )
                        result_status = "queued"
                    elif kind == "webhook":
                        integration = await workflow_repository.connected_integration(
                            db, event.organization_id, action["integration_id"]
                        )
                        if not integration:
                            raise NotFoundError(message="Workflow integration not found")
                        await workflow_repository.enqueue_integration_delivery(
                            db,
                            integration=integration,
                            event=event,
                            workflow=workflow,
                            action_index=action_index,
                            payload={
                                "workflow_id": workflow.id,
                                "event_id": event.id,
                                "module": event.module,
                                "trigger": event.trigger,
                                "entity_id": event.entity_id,
                                "data": event.payload,
                            },
                        )
                        result_status = "queued"
                    result = {
                        "action_index": action_index,
                        "type": kind,
                        "status": result_status,
                    }
                    run.action_results = [*results, result]
                    await db.commit()
                    results.append(result)
                run.action_results = results
                run.status = "Completed"
                run.finished_at = datetime.now(UTC)
                await db.commit()
            except Exception as exc:
                await db.rollback()
                run = await db.get(WorkflowRun, run_id)
                await self._record_failed_run(
                    db,
                    event_id,
                    workflow_id,
                    run,
                    type(exc).__name__,
                    results,
                )
                raise
        event = await db.get(WorkflowEvent, event_id)
        event.status = "Completed"
        event.claimed_at = None
        event.processed_at = datetime.now(UTC)
        await db.commit()

    async def _record_failed_run(
        self,
        db,
        event_id: str,
        workflow_id: str,
        run,
        error: str,
        results: list[dict] | None = None,
    ):
        if run is None:
            run = WorkflowRun(
                event_id=event_id,
                workflow_id=workflow_id,
                status="Failed",
                action_results=list(results) if results is not None else [],
            )
            db.add(run)
        run.status = "Failed"
        run.action_results = (
            list(results) if results is not None else list(run.action_results or [])
        )
        run.error = error[:500]
        run.finished_at = datetime.now(UTC)
        await db.commit()


workflow_service = WorkflowService()
