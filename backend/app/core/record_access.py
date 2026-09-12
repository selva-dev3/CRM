from dataclasses import dataclass

from sqlalchemy import false, or_
from sqlalchemy.sql.elements import ColumnElement


@dataclass(frozen=True)
class RecordAccessContext:
    scope: str
    user_id: str
    team_ids: frozenset[str]
    team_user_ids: frozenset[str]


def record_access_filter(
    context: RecordAccessContext | None,
    *,
    assigned_column=None,
    created_column=None,
    team_column=None,
) -> ColumnElement[bool] | None:
    if context is None or context.scope == "all":
        return None
    if context.scope == "none":
        return false()
    if context.scope == "own":
        return created_column == context.user_id if created_column is not None else false()
    if context.scope == "assigned":
        return assigned_column == context.user_id if assigned_column is not None else false()
    if context.scope == "team":
        predicates = []
        if assigned_column is not None:
            predicates.append(assigned_column.in_(context.team_user_ids))
        if team_column is not None:
            predicates.append(team_column.in_(context.team_ids))
        return or_(*predicates) if predicates else false()
    return false()
