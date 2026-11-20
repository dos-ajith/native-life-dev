import json
from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.exceptions import NotFoundError
from app.core.messages import DocsMessages

DOCS_DIRECTORY = Path(__file__).resolve().parents[2] / "docs"
WEBSOCKET_DOCS_MARKDOWN_PATH = DOCS_DIRECTORY / "websocket-api.md"
PAYMENT_DOCS_MARKDOWN_PATH = DOCS_DIRECTORY / "payments.md"
DOCS_PAGE_PATH = Path(__file__).with_name("markdown_docs.html")
MARKDOWN_PLACEHOLDER = "__MARKDOWN_JSON__"
TITLE_PLACEHOLDER = "__PAGE_TITLE__"
NAV_PLACEHOLDER = "__NAV_LINKS__"
WEBSOCKET_DOCS_TITLE = "Native Life — WebSocket API Documentation"
PAYMENT_DOCS_TITLE = "Native Life — Payment Integration Guide"
NAV_PAGES = (
    ("/docs", "REST API (Swagger)"),
    ("/websocket-docs", "WebSocket API"),
    ("/payment-docs", "Payments (Razorpay)"),
)

router = APIRouter(tags=["docs"])


def _nav_links(current_path: str) -> str:
    return "<br>".join(
        f"{escape(label)} (this page)"
        if path == current_path
        else f'<a href="{path}">{escape(label)}</a>'
        for path, label in NAV_PAGES
    )


def _render(markdown_path: Path, title: str, current_path: str, missing: str) -> HTMLResponse:
    if not markdown_path.is_file():
        raise NotFoundError(missing)
    markdown = markdown_path.read_text(encoding="utf-8")
    embedded_markdown = json.dumps(markdown).replace("<", "\\u003c")
    page = (
        DOCS_PAGE_PATH.read_text(encoding="utf-8")
        .replace(TITLE_PLACEHOLDER, escape(title))
        .replace(NAV_PLACEHOLDER, _nav_links(current_path))
    )
    return HTMLResponse(page.replace(MARKDOWN_PLACEHOLDER, embedded_markdown))


@router.get("/websocket-docs", response_class=HTMLResponse, include_in_schema=False)
def websocket_docs() -> HTMLResponse:
    return _render(
        WEBSOCKET_DOCS_MARKDOWN_PATH,
        WEBSOCKET_DOCS_TITLE,
        "/websocket-docs",
        DocsMessages.WEBSOCKET_DOCS_NOT_FOUND,
    )


@router.get("/payment-docs", response_class=HTMLResponse, include_in_schema=False)
def payment_docs() -> HTMLResponse:
    return _render(
        PAYMENT_DOCS_MARKDOWN_PATH,
        PAYMENT_DOCS_TITLE,
        "/payment-docs",
        DocsMessages.PAYMENT_DOCS_NOT_FOUND,
    )
