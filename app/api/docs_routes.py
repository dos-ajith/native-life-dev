from typing import Any

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from app.core.openapi_audiences import AUDIENCES, DocsAudience, audience_openapi

router = APIRouter(include_in_schema=False)


@router.get("/openapi/{audience}.json")
def audience_openapi_schema(audience: DocsAudience, request: Request) -> dict[str, Any]:
    return audience_openapi(request.app.openapi(), audience)


@router.get("/docs/{audience}", response_class=HTMLResponse)
def audience_swagger_ui(audience: DocsAudience, request: Request) -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=f"/openapi/{audience.value}.json",
        title=f"{request.app.title} · {AUDIENCES[audience].title}",
    )
