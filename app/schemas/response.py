from pydantic import BaseModel


class SuccessResponse[T](BaseModel):
    success: bool = True
    message: str
    data: T
