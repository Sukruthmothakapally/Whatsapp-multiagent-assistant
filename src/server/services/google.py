from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pickle
from typing import List, Dict, Any, Optional
from pathlib import Path

from server.config import google_settings
from server.models import EmailResponse, EventResponse, TaskResponse


class GoogleService:
    """Service for interacting with Google APIs"""
    
    @staticmethod
    def get_credentials():
        """Load saved credentials from token file"""
        try:
            with open(google_settings.token_file, "rb") as token:
                return pickle.load(token)
        except Exception as e:
            raise Exception(f"Failed to load credentials: {str(e)}")
    
    @classmethod
    def get_recent_emails(cls, max_results: int = 10) -> List[EmailResponse]:
        """
        Fetch emails from the last 24 hours
        Returns: List of dicts with sender, subject, and body snippet
        """
        creds = cls.get_credentials()
        service = build("gmail", "v1", credentials=creds)
        
        # Calculate 24 hours ago in RFC 3339 format
        one_day_ago = (datetime.utcnow() - timedelta(days=1)).strftime('%Y/%m/%d')
        
        # Query for messages in INBOX from the last 24 hours
        query = f"in:inbox after:{one_day_ago}"
        
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get("messages", [])
        
        if not messages:
            return []
        
        emails = []
        for msg in messages:
            # Get full message details
            detail = service.users().messages().get(
                userId="me", 
                id=msg["id"], 
                format="full"
            ).execute()
            
            payload = detail.get("payload", {})
            headers = payload.get("headers", [])
            
            # Extract subject
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")
            
            # Extract sender
            sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "(Unknown Sender)")
            
            # Get body snippet
            body = detail.get("snippet", "")
            
            emails.append(EmailResponse(
                sender=sender,
                subject=subject,
                body=body,
                timestamp=detail.get("internalDate")
            ))
        
        return emails
    
    @classmethod
    def get_todays_events(cls) -> List[EventResponse]:
        """
        Fetch calendar events for today only
        Returns: List of event details
        """
        creds = cls.get_credentials()
        service = build("calendar", "v3", credentials=creds)
        
        # Get today's date range in UTC
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        today_end = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999).isoformat() + "Z"
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=today_start,
            timeMax=today_end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        event_list = []
        for event in events:
            event_list.append(EventResponse(
                id=event.get("id", ""),
                summary=event.get("summary", "(No Title)"),
                start=event["start"].get("dateTime", event["start"].get("date")),
                end=event["end"].get("dateTime", event["end"].get("date")),
                location=event.get("location", ""),
                description=event.get("description", ""),
                organizer=event.get("organizer", {}).get("email", "")
            ))
        
        return event_list
    
    @classmethod
    def get_due_tasks(cls) -> List[TaskResponse]:
        """
        Fetch all tasks (without date filtering)
        Returns: List of task details
        """
        creds = cls.get_credentials()
        service = build("tasks", "v1", credentials=creds)
        
        # Get all task lists
        tasklists = service.tasklists().list().execute()
        
        all_tasks = []
        for tasklist in tasklists.get("items", []):
            list_id = tasklist["id"]
            list_title = tasklist["title"]
            
            # Get tasks from each list
            tasks = service.tasks().list(
                tasklist=list_id,
                showCompleted=False,  # Only show incomplete tasks
                showHidden=False
            ).execute()
            
            for task in tasks.get("items", []):
                all_tasks.append(TaskResponse(
                    id=task.get("id", ""),
                    title=task.get("title", ""),
                    notes=task.get("notes", ""),
                    due=task.get("due", ""),
                    status=task.get("status", ""),
                    list_name=list_title
                ))
        
        return all_tasks


google_service = GoogleService()