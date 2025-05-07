from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
import pickle

from server.config import google_settings
from server.services.google import google_service
from server.models import (
    EmailsListResponse, 
    EventsListResponse, 
    TasksListResponse, 
    OAuthResponse,
    ErrorResponse, 
    EmailSendResponse,
    EmailRequest,
    TaskCreateResponse,
    TaskRequest,
    EventCreateResponse,
    EventRequest
)

router = APIRouter(
    prefix="/api/google",
    tags=["google"],
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)


@router.get("/auth", response_class=RedirectResponse)
async def google_auth():
    """Initiate Google OAuth flow"""
    flow = Flow.from_client_secrets_file(
        google_settings.client_secrets_file,
        scopes=google_settings.scopes,
        redirect_uri=google_settings.redirect_uri
    )
    auth_url, _ = flow.authorization_url(
        prompt='consent',
        access_type='offline',
        include_granted_scopes='true'
    )
    return RedirectResponse(auth_url)


@router.get("/oauth/callback", response_model=OAuthResponse)
async def oauth_callback(request: Request):
    """Handle OAuth callback from Google"""
    try:
        # Extract full URL with query params
        url = str(request.url)

        # Recreate flow to fetch token
        flow = Flow.from_client_secrets_file(
            google_settings.client_secrets_file,
            scopes=google_settings.scopes,
            redirect_uri=google_settings.redirect_uri
        )
        flow.fetch_token(authorization_response=url)

        # Save credentials to file
        credentials = flow.credentials
        with open(google_settings.token_file, "wb") as f:
            pickle.dump(credentials, f)

        return OAuthResponse(
            status="✅ Google OAuth complete",
            token_expiry=str(credentials.expiry),
            scopes=credentials.scopes
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"OAuth error: {str(e)}"
        )


@router.get("/gmail/me", response_model=EmailsListResponse)
async def get_gmail_messages():
    """
    Get Gmail messages from the last 24 hours with sender, subject, and body details
    """
    try:
        # Use the service to get recent emails
        emails = google_service.get_recent_emails()
        
        return EmailsListResponse(
            status="success",
            count=len(emails),
            emails=emails
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Gmail API error: {str(e)}"
        )


@router.get("/calendar/me", response_model=EventsListResponse)
async def get_calendar_events():
    """
    Get calendar events for today only
    """
    try:
        # Use the service to get today's events
        events = google_service.get_todays_events()
        
        return EventsListResponse(
            status="success",
            count=len(events),
            events=events
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Calendar API error: {str(e)}"
        )



@router.get("/tasks/me", response_model=TasksListResponse)
async def get_google_tasks():
    """
    Get all tasks (without date filtering)
    """
    try:
        # Use the service to get all tasks
        tasks = google_service.get_due_tasks()
        
        return TasksListResponse(
            status="success", 
            count=len(tasks),
            tasks=tasks
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Tasks API error: {str(e)}"
        )


@router.post("/gmail/send", response_model=EmailSendResponse)
async def send_gmail_message(email_data: EmailRequest):
    """
    Send an email via Gmail API
    """
    try:
        # Use the service to send an email
        message_id = google_service.send_email(
            to=email_data.to,
            subject=email_data.subject,
            body=email_data.body,
            cc=email_data.cc,
            bcc=email_data.bcc
        )
        
        return EmailSendResponse(
            status="success",
            message="Email sent successfully",
            message_id=message_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Gmail API error: {str(e)}"
        )
    
@router.post("/calendar/events", response_model=EventCreateResponse)
async def create_calendar_event(event_data: EventRequest):
    """
    Create a new calendar event
    """
    try:
        # Use the service to create a calendar event
        event_id = google_service.create_calendar_event(
            summary=event_data.summary,
            location=event_data.location,
            description=event_data.description,
            start_time=event_data.start_time,
            end_time=event_data.end_time,
            attendees=event_data.attendees,
            calendar_id=event_data.calendar_id or 'primary'
        )
        
        return EventCreateResponse(
            status="success",
            message="Event created successfully",
            event_id=event_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Calendar API error: {str(e)}"
        )
    

@router.post("/tasks/create", response_model=TaskCreateResponse)
async def create_task(task_data: TaskRequest):
    """
    Create a new task in Google Tasks
    """
    try:
        # Use the service to create a task
        task_id = google_service.create_task(
            title=task_data.title,
            notes=task_data.notes,
            due_date=task_data.due_date,
            task_list_id=task_data.task_list_id or '@default'
        )
        
        return TaskCreateResponse(
            status="success",
            message="Task created successfully",
            task_id=task_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Tasks API error: {str(e)}"
        )