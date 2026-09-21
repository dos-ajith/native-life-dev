from typing import Annotated

from pydantic import BaseModel, Field

UtmSource = Annotated[str, Field(max_length=100)]


class PostShareCreate(BaseModel):
    utm_source: UtmSource | None = None
