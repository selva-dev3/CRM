from fastapi.routing import APIRoute

from app.api.v1.routers import settings
from app.schemas.crm_schemas import CustomFieldResponse


def test_list_custom_fields_declares_response_model() -> None:
    route = next(
        route
        for route in settings.router.routes
        if isinstance(route, APIRoute)
        and route.path == "/custom-fields"
        and "GET" in (route.methods or set())
    )

    assert route.response_model == list[CustomFieldResponse]
