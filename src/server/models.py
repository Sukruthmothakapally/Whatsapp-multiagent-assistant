from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class MessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class MessageResponse(BaseModel):
    reply: str


class EmailResponse(BaseModel):
    """Model for email response data"""
    sender: str
    subject: str
    body: str
    timestamp: Optional[str] = None


class EmailsListResponse(BaseModel):
    """Model for a list of emails"""
    status: str
    count: int
    emails: List[EmailResponse]


class EventResponse(BaseModel):
    """Model for calendar event data"""
    id: str
    summary: str
    start: str
    end: str
    location: Optional[str] = None
    description: Optional[str] = None
    organizer: Optional[str] = None


class EventsListResponse(BaseModel):
    """Model for a list of events"""
    status: str
    count: int
    events: List[EventResponse]


class TaskResponse(BaseModel):
    """Model for task data"""
    id: str
    title: str
    notes: Optional[str] = None
    due: Optional[str] = None
    status: str
    list_name: str


class TasksListResponse(BaseModel):
    """Model for a list of tasks"""
    status: str
    count: int
    tasks: List[TaskResponse]


class OAuthResponse(BaseModel):
    """Model for OAuth completion response"""
    status: str
    token_expiry: str
    scopes: List[str]


class ErrorResponse(BaseModel):
    """Model for error responses"""
    error: str
