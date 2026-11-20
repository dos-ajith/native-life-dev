from app.ai.tools.base import AITool
from app.ai.tools.base import ToolContext as AIToolContext
from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep, require_permission
from app.core.exceptions import AuthorizationError, BusinessRuleError, ConflictError, NotFoundError
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User
from app.plugins.activity import record_activity
from app.plugins.approvals import notify_approval_decided, notify_approval_requested
from app.plugins.booking import BookableItem, BookingProvider
from app.plugins.businesses import (
    NativeOrigin,
    category_slugs_for_businesses,
    find_native_origin,
    find_plugin_business,
)
from app.plugins.context import PluginContext
from app.plugins.deal_commerce import DealCommerceProvider, DealProduct, StockLine
from app.plugins.deps import PluginBusiness, require_business_plugin
from app.plugins.media import (
    StoredImage,
    StoredVideo,
    delete_plugin_image,
    delete_plugin_video,
    save_plugin_image,
    save_plugin_video,
)
from app.plugins.orders import OrderSummary, find_order_summaries
from app.plugins.versioning import CORE_API_VERSION
from app.schemas.base import BaseReadSchema
from app.schemas.pagination import Page, PaginationParams
from app.schemas.response import SuccessResponse
from app.services.plugin_business_discovery_service import (
    NativeBusinessScope,
    NearbyBusiness,
    find_businesses_near_native_places,
)

SDK_VERSION = CORE_API_VERSION

__all__ = [
    "SDK_VERSION",
    "AITool",
    "AIToolContext",
    "AuthorizationError",
    "BookableItem",
    "BookingProvider",
    "BaseReadSchema",
    "BusinessRuleError",
    "ConflictError",
    "CurrentActiveUserDep",
    "DbSessionDep",
    "DealCommerceProvider",
    "DealProduct",
    "NativeBusinessScope",
    "NativeOrigin",
    "NearbyBusiness",
    "NotFoundError",
    "OrderSummary",
    "Page",
    "PaginationDep",
    "PaginationParams",
    "PluginBusiness",
    "PluginContext",
    "StockLine",
    "StoredImage",
    "StoredVideo",
    "SuccessResponse",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "delete_plugin_image",
    "category_slugs_for_businesses",
    "delete_plugin_video",
    "find_businesses_near_native_places",
    "find_native_origin",
    "find_order_summaries",
    "find_plugin_business",
    "notify_approval_decided",
    "notify_approval_requested",
    "record_activity",
    "require_business_plugin",
    "require_permission",
    "save_plugin_image",
    "save_plugin_video",
]
