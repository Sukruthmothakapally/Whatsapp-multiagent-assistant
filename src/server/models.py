from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

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


class EmailRequest(BaseModel):
    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None

class EmailSendResponse(BaseModel):
    status: str
    message: str
    message_id: str

class EventRequest(BaseModel):
    summary: str
    location: Optional[str] = None
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    attendees: Optional[List[str]] = None
    calendar_id: Optional[str] = None  # Default to 'primary' in the service

class EventCreateResponse(BaseModel):
    status: str
    message: str
    event_id: str

class TaskRequest(BaseModel):
    title: str
    notes: Optional[str] = None
    due_date: Optional[datetime] = None
    task_list_id: Optional[str] = None  # Default to '@default' in the service

class TaskCreateResponse(BaseModel):
    status: str
    message: str
    task_id: str