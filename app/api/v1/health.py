from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.deps import DbSessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def readiness(db: DbSessionDep, response: Response) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}
