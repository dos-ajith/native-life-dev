from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1.admin import geography as admin_geography_routes
from app.api.v1.admin import routes as admin_routes
from app.api.v1.ai import routes as ai_routes
from app.api.v1.auth import routes as auth_routes
from app.api.v1.geography import routes as geography_routes
from app.api.v1.pages import routes as page_routes
from app.api.v1.permissions import routes as permission_routes
from app.api.v1.posts import comments as post_comment_routes
from app.api.v1.posts import likes as post_like_routes
from app.api.v1.posts import routes as post_routes
from app.api.v1.posts import shares as post_share_routes
from app.api.v1.roles import routes as role_routes
from app.api.v1.settings import routes as setting_routes
from app.api.v1.users import routes as user_routes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ai_routes.router)
api_router.include_router(auth_routes.router)
api_router.include_router(admin_routes.router)
api_router.include_router(admin_geography_routes.router)
api_router.include_router(geography_routes.router)
api_router.include_router(role_routes.router)
api_router.include_router(permission_routes.router)
api_router.include_router(setting_routes.router)
api_router.include_router(user_routes.router)
api_router.include_router(page_routes.router)
api_router.include_router(post_routes.router)
api_router.include_router(post_comment_routes.router)
api_router.include_router(post_like_routes.router)
api_router.include_router(post_share_routes.router)
