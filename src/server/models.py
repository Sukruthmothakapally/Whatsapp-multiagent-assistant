from pydantic import BaseModel
from typing import Optional


class MessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class MessageResponse(BaseModel):
    reply: str
