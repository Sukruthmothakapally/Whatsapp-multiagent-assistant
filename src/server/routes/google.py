from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from pathlib import Path
import pickle
import os

router = APIRouter()

# Path to OAuth client secret
BASE_DIR = Path(__file__).resolve().parents[3]  # Adjust the level based on your structure
CLIENT_SECRETS_FILE = str(BASE_DIR / "client_secret.json")

# Scopes (Gmail, Calendar, Tasks Read-Only)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks.readonly"
]

# Must match exactly what you set in Google Cloud Console
REDIRECT_URI = "https://b1a7-73-231-49-218.ngrok-free.app/oauth/callback"

# Save tokens here
TOKEN_FILE = BASE_DIR / "google_token.pickle"

@router.get("/google/auth")
async def google_auth():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        prompt='consent',
        access_type='offline',
        include_granted_scopes='true'
    )
    return RedirectResponse(auth_url)


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    try:
        # Extract full URL with query params
        url = str(request.url)

        # Recreate flow to fetch token
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(authorization_response=url)

        # Save credentials to file
        credentials = flow.credentials
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(credentials, f)

        return JSONResponse({
            "status": "✅ Google OAuth complete",
            "token_expiry": str(credentials.expiry),
            "scopes": credentials.scopes
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/gmail/me")
async def get_gmail_subjects():
    try:
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(userId="me", maxResults=5).execute()
        messages = results.get("messages", [])

        if not messages:
            return {"status": "No messages found"}

        subjects = []
        for msg in messages:
            detail = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["Subject"]).execute()
            headers = detail.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
            subjects.append(subject)

        return {"subjects": subjects}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/calendar/me")
async def get_calendar_events():
    try:
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

        service = build("calendar", "v3", credentials=creds)

        events_result = service.events().list(
            calendarId='primary',
            maxResults=5,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        event_list = []
        for event in events:
            summary = event.get("summary", "(No Title)")
            start = event["start"].get("dateTime", event["start"].get("date"))
            event_list.append({"summary": summary, "start": start})

        return {"events": event_list}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/tasks/me")
async def get_google_tasks():
    try:
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

        service = build("tasks", "v1", credentials=creds)

        # Get task lists (you can have multiple like "My Tasks", "Work", etc.)
        tasklists = service.tasklists().list(maxResults=1).execute()
        if not tasklists.get("items"):
            return {"status": "No task lists found"}

        first_list_id = tasklists["items"][0]["id"]

        # Get tasks from the first list
        tasks = service.tasks().list(tasklist=first_list_id, maxResults=5).execute()
        task_items = tasks.get("items", [])

        task_list = []
        for task in task_items:
            task_list.append({
                "title": task.get("title"),
                "status": task.get("status"),
                "due": task.get("due"),
                "notes": task.get("notes")
            })

        return {"tasks": task_list}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)