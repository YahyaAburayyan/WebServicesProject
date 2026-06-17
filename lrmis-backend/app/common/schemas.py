from typing import Annotated, Any, Generic, TypeVar

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator


def _validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError(f"Invalid ObjectId: {v!r}")


PyObjectId = Annotated[str, BeforeValidator(_validate_object_id)]

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    limit: int


class Message(BaseModel):
    message: str
