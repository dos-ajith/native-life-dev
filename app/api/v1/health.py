from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.deps import DbSessionDep
from app.core.exceptions import ServiceUnavailableError
from app.core.messages import HealthMessages
from app.schemas.response import SuccessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=SuccessResponse[dict[str, str]])
def liveness() -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(message=HealthMessages.SERVICE_HEALTHY, data={"status": "ok"})


@router.get("/health/ready", response_model=SuccessResponse[dict[str, str]])
def readiness(db: DbSessionDep) -> SuccessResponse[dict[str, str]]:
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        raise ServiceUnavailableError(HealthMessages.DATABASE_UNAVAILABLE) from exc
    return SuccessResponse(message=HealthMessages.DATABASE_HEALTHY, data={"status": "ok"})
