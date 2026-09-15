from sqlalchemy import exists, false, or_, select

from app.core.record_access import RecordAccessContext, record_access_filter
from app.models import Project, ProjectMember, Task


def project_record_access_filter(
    access: RecordAccessContext | None,
    *,
    project_id_column=Project.id,
    linked: bool = False,
):
    """Authorize a project through ownership or an assigned project task."""
    base = record_access_filter(
        access,
        assigned_column=Project.owner_id,
        created_column=Project.created_by,
    )
    if access is None or access.scope == "all":
        return None
    if access.scope == "none":
        result = base
        return (
            exists(select(Project.id).where(Project.id == project_id_column, result))
            if linked and result is not None
            else result
        )
    assignees = (
        (access.user_id,) if access.scope in {"own", "assigned"} else tuple(access.team_user_ids)
    )
    if not assignees:
        return base if base is not None else false()
    task_access = exists(
        select(Task.id).where(
            Task.project_id == project_id_column,
            Task.assigned_to.in_(assignees),
        )
    )
    member_access = exists(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id_column,
            ProjectMember.user_id.in_(assignees),
        )
    )
    linked_access = or_(task_access, member_access)
    result = or_(base, linked_access) if base is not None else linked_access
    return (
        exists(select(Project.id).where(Project.id == project_id_column, result))
        if linked
        else result
    )
