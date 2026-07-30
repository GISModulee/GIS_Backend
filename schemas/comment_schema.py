from pydantic import BaseModel


class CommentCreate(BaseModel):
    feature_id: int
    user_id: int
    comment: str

from pydantic import BaseModel


class CommentCreate(BaseModel):
    feature_id: int
    user_id: int
    comment: str
