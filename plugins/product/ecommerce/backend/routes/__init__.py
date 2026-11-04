from .explore import router as explore_router
from .inventory import router as inventory_router
from .products import router as products_router
from .settings import router as settings_router

ROUTERS = (explore_router, products_router, inventory_router, settings_router)
