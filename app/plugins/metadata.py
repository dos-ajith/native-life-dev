from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase

from app.core.messages import PluginMessages
from app.models.base import Base as CoreBase
from app.plugins.errors import PluginError


def ensure_isolated_base(base: type[DeclarativeBase], table_prefix: str) -> None:
    if base.registry is CoreBase.registry or base.metadata is CoreBase.metadata:
        raise PluginError(PluginMessages.MODEL_BASE_NOT_ISOLATED)
    for table_name in base.metadata.tables:
        if not table_name.startswith(table_prefix):
            raise PluginError(
                PluginMessages.TABLE_PREFIX_VIOLATION.format(table=table_name, prefix=table_prefix)
            )


def configure_isolated(base: type[DeclarativeBase]) -> None:
    try:
        base.registry.configure(cascade=True)
    except SQLAlchemyError as exc:
        base.registry.dispose()
        raise PluginError(
            PluginMessages.MAPPER_CONFIGURATION_FAILED.format(error=type(exc).__name__)
        ) from exc
