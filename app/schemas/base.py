from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, SerializerFunctionWrapHandler, model_serializer

from app.core.formatting_context import get_datetime_formats
from app.utils.datetime_format import format_datetime


class BaseReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def _serialize_datetime_fields(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        date_format, time_format = get_datetime_formats()
        for field_name in data:
            value = getattr(self, field_name, None)
            if isinstance(value, datetime):
                data[field_name] = format_datetime(value, date_format, time_format)
        return data
