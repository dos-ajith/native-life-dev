from app.schemas.pagination import Page, PaginationParams


def test_page_create_computes_page_count() -> None:
    params = PaginationParams(page=1, page_size=10)

    page = Page[str].create(items=["a", "b"], total=25, params=params)

    assert page.pages == 3
    assert page.total == 25
    assert page.items == ["a", "b"]


def test_page_create_handles_empty_results() -> None:
    params = PaginationParams(page=1, page_size=10)

    page = Page[str].create(items=[], total=0, params=params)

    assert page.pages == 0
