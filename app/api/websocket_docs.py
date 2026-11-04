import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.exceptions import NotFoundError
from app.core.messages import DocsMessages

WEBSOCKET_DOCS_MARKDOWN_PATH = Path(__file__).resolve().parents[2] / "docs" / "websocket-api.md"
WEBSOCKET_DOCS_PAGE_PATH = Path(__file__).with_name("websocket_docs.html")
MARKDOWN_PLACEHOLDER = "__MARKDOWN_JSON__"

router = APIRouter(tags=["docs"])


@router.get("/websocket-docs", response_class=HTMLResponse, include_in_schema=False)
def websocket_docs() -> HTMLResponse:
    if not WEBSOCKET_DOCS_MARKDOWN_PATH.is_file():
        raise NotFoundError(DocsMessages.WEBSOCKET_DOCS_NOT_FOUND)
    markdown = WEBSOCKET_DOCS_MARKDOWN_PATH.read_text(encoding="utf-8")
    embedded_markdown = json.dumps(markdown).replace("<", "\\u003c")
    page = WEBSOCKET_DOCS_PAGE_PATH.read_text(encoding="utf-8")
    return HTMLResponse(page.replace(MARKDOWN_PLACEHOLDER, embedded_markdown))
