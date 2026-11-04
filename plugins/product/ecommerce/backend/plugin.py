from app.plugins.sdk import PluginContext

from .ai_tools import EcommerceSearchProductsTool
from .deal_commerce import EcommerceDealCommerce
from .models import EcommerceBase
from .routes import ROUTERS


def register(ctx: PluginContext) -> None:
    ctx.register_models(EcommerceBase)
    ctx.register_ai_tool(EcommerceSearchProductsTool())
    ctx.register_deal_commerce(EcommerceDealCommerce())
    for router in ROUTERS:
        ctx.include_router(router)
