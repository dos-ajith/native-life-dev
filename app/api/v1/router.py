from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1.auth import routes as auth_routes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_routes.router)
