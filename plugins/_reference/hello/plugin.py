from app.plugins.sdk import PluginContext

from .routes import router


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
