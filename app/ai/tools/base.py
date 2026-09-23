from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, ClassVar

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_settings_enums import AIResponseStyle
from app.schemas.validators import NonBlankStr

SearchQuery = Annotated[NonBlankStr, Field(max_length=100)]


@dataclass(frozen=True)
class ToolContext:
    db: Session
    actor: User
    ai_enabled: bool
    personalization_enabled: bool
    preferred_language: str
    response_style: AIResponseStyle


class AITool[ArgsT: BaseModel](ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    args_model: type[ArgsT]

    @abstractmethod
    def execute(self, context: ToolContext, arguments: ArgsT) -> BaseModel:
        raise NotImplementedError
