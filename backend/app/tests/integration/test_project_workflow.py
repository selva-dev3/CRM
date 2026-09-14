import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import func, select
from starlette.datastructures import Headers, UploadFile

from app.core.errors import APIException
from app.models.task import TaskDependency
from app.schemas.crm_schemas import TaskCreate
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.document_service import DocumentService
from app.services.milestone_service import MilestoneService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.tests.integration.test_sales_quote_workflow import sales_database as sales_database


@pytest.mark.asyncio
async def test_project_members_tasks_dependencies_milestones_documents_and_completion(
    sales_database, monkeypatch
):
    sessions, org, user, company, contact, _, deal = sales_database
    monkeypatch.setattr(
        "app.services.project_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["projects:assign"]),
    )
    project_service = ProjectService()
    task_service = TaskService()
    milestone_service = MilestoneService()

    async with sessions() as db:
        project = await project_service.create_project(
            db,
            user,
            ProjectCreate(
                name="Customer rollout",
                company_id=company.id,
                contact_id=contact.id,
                originating_deal_id=deal.id,
                start_date="2026-09-01",
                due_date="2026-10-01",
            ),
        )
        project_id = project["id"]
        members = await project_service.list_members(db, user, project_id)
        assert [(member["user_id"], member["role"]) for member in members] == [
            (user.id, "Manager")
        ]

        prerequisite = await task_service.create_task(
            db,
            TaskCreate(
                title="Prepare environment",
                project_id=project_id,
                due_date="2026-09-10",
            ),
            user,
        )
        dependent = await task_service.create_task(
            db,
            TaskCreate(
                title="Launch customer",
                project_id=project_id,
                due_date="2026-09-20",
            ),
            user,
        )
        await task_service.add_dependency(
            db, dependent["id"], prerequisite["id"], org.id, user
        )
        with pytest.raises(APIException, match="dependencies"):
            await task_service.complete_task(db, dependent["id"], org.id, user)
        await db.rollback()
        await task_service.complete_task(db, prerequisite["id"], org.id, user)
        await task_service.complete_task(db, dependent["id"], org.id, user)

        milestone = await milestone_service.create(
            db,
            user,
            MilestoneCreate(
                project_id=project_id,
                name="Customer acceptance",
                due_date="2026-09-25",
            ),
        )
        partially_complete = await project_service.get_project(db, user, project_id)
        assert partially_complete["completion_percentage"] == 67
        await milestone_service.update(
            db, user, milestone["id"], MilestoneUpdate(status="Completed")
        )
        ready = await project_service.get_project(db, user, project_id)
        assert ready["completion_percentage"] == 100

    monkeypatch.setattr(
        "app.services.document_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["documents:read", "projects:read"]),
    )
    monkeypatch.setattr(
        "app.services.document_service.s3_service.upload_file",
        Mock(return_value=f"documents/{org.id}/project-plan.txt"),
    )
    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        Mock(return_value="https://storage.example.test/project-plan.txt"),
    )
    upload = UploadFile(
        filename="project-plan.txt",
        file=BytesIO(b"project plan"),
        headers=Headers({"content-type": "text/plain"}),
        size=12,
    )
    async with sessions() as db:
        document = await DocumentService().upload_document(
            db, upload, current_user=user, project_id=project_id
        )
        assert document["project_id"] == project_id
        listed = await DocumentService().list_documents(
            db,
            page=1,
            limit=20,
            project_id=project_id,
            current_user=user,
        )
        assert [item["id"] for item in listed] == [document["id"]]
        completed = await project_service.update_project(
            db, user, project_id, ProjectUpdate(status="Completed")
        )
        assert completed["status"] == "Completed"
        assert completed["completion_percentage"] == 100


@pytest.mark.asyncio
async def test_concurrent_reciprocal_task_dependencies_cannot_create_cycle(
    sales_database, monkeypatch
):
    sessions, org, user, company, contact, _, deal = sales_database
    monkeypatch.setattr(
        "app.services.project_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["projects:assign"]),
    )
    async with sessions() as db:
        project = await ProjectService().create_project(
            db,
            user,
            ProjectCreate(
                name="Concurrent dependency test",
                company_id=company.id,
                contact_id=contact.id,
                originating_deal_id=deal.id,
                start_date="2026-09-01",
                due_date="2026-10-01",
            ),
        )
        first = await TaskService().create_task(
            db, TaskCreate(title="First", project_id=project["id"]), user
        )
        second = await TaskService().create_task(
            db, TaskCreate(title="Second", project_id=project["id"]), user
        )

    async def add_dependency(task_id: str, dependency_id: str):
        async with sessions() as db:
            return await TaskService().add_dependency(
                db, task_id, dependency_id, org.id, user
            )

    results = await asyncio.gather(
        add_dependency(first["id"], second["id"]),
        add_dependency(second["id"], first["id"]),
        return_exceptions=True,
    )

    assert sum(isinstance(result, APIException) for result in results) == 1
    error = next(result for result in results if isinstance(result, APIException))
    assert error.status_code == 409
    async with sessions() as db:
        edge_count = await db.scalar(
            select(func.count()).select_from(TaskDependency).where(
                TaskDependency.task_id.in_([first["id"], second["id"]])
            )
        )
    assert edge_count == 1
