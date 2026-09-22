from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.user import User


@dataclass(frozen=True)
class ToolContext:
    db: Session
    actor: User


class AITool[ArgsT: BaseModel](ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    args_model: type[ArgsT]

    @abstractmethod
    def execute(self, context: ToolContext, arguments: ArgsT) -> BaseModel:
        raise NotImplementedError
