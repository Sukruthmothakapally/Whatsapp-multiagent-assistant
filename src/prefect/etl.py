from prefect import flow, task
from prefect.logging import get_run_logger
import httpx
import json
import os
from datetime import datetime
from pathlib import Path

# Base URL for the API
BASE_URL = "http://localhost:8000"  # Change if your server runs on a different port

@task(name="Fetch Gmail Messages", retries=3, retry_delay_seconds=5)
async def fetch_gmail_messages():
    """
    Fetch Gmail messages from the last 24 hours
    """
    logger = get_run_logger()
    logger.info("Fetching Gmail messages")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/google/gmail/me")
        if response.status_code != 200:
            logger.error(f"Failed to fetch Gmail messages: {response.text}")
            raise Exception(f"Failed to fetch Gmail messages: {response.text}")
        
        logger.info(f"Successfully fetched {response.json().get('count', 0)} Gmail messages")
        return response.json()

@task(name="Filter Gmail Data")
def filter_gmail_data(gmail_data):
    """
    Filter Gmail data to only include required fields
    """
    logger = get_run_logger()
    logger.info("Filtering Gmail data")
    
    filtered_emails = []
    for email in gmail_data.get("emails", []):
        filtered_emails.append({
            "sender": email.get("sender"),
            "subject": email.get("subject"),
            "body": email.get("body"),
            "timestamp": email.get("timestamp")
        })
    
    logger.info(f"Filtered {len(filtered_emails)} Gmail messages")
    return {
        "count": gmail_data.get("count", 0),
        "emails": filtered_emails
    }

@task(name="Fetch Calendar Events", retries=3, retry_delay_seconds=5)
async def fetch_calendar_events():
    """
    Fetch today's calendar events
    """
    logger = get_run_logger()
    logger.info("Fetching Calendar events")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/google/calendar/me")
        if response.status_code != 200:
            logger.error(f"Failed to fetch Calendar events: {response.text}")
            raise Exception(f"Failed to fetch Calendar events: {response.text}")
        
        logger.info(f"Successfully fetched {response.json().get('count', 0)} Calendar events")
        return response.json()

@task(name="Filter Calendar Data")
def filter_calendar_data(calendar_data):
    """
    Filter calendar data to only include required fields
    """
    logger = get_run_logger()
    logger.info("Filtering Calendar data")
    
    filtered_events = []
    for event in calendar_data.get("events", []):
        filtered_events.append({
            "summary": event.get("summary"),
            "start": event.get("start"),
            "end": event.get("end"),
            "location": event.get("location"),
            "description": event.get("description")
        })
    
    logger.info(f"Filtered {len(filtered_events)} Calendar events")
    return {
        "count": calendar_data.get("count", 0),
        "events": filtered_events
    }

@task(name="Fetch Tasks", retries=3, retry_delay_seconds=5)
async def fetch_tasks():
    """
    Fetch all tasks
    """
    logger = get_run_logger()
    logger.info("Fetching Tasks")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/google/tasks/me")
        if response.status_code != 200:
            logger.error(f"Failed to fetch Tasks: {response.text}")
            raise Exception(f"Failed to fetch Tasks: {response.text}")
        
        logger.info(f"Successfully fetched {response.json().get('count', 0)} Tasks")
        return response.json()

@task(name="Filter Tasks Data")
def filter_tasks_data(tasks_data):
    """
    Filter tasks data to only include required fields
    """
    logger = get_run_logger()
    logger.info("Filtering Tasks data")
    
    filtered_tasks = []
    for task in tasks_data.get("tasks", []):
        filtered_tasks.append({
            "title": task.get("title"),
            "notes": task.get("notes"),
            "due": task.get("due"),
            "status": task.get("status")
        })
    
    logger.info(f"Filtered {len(filtered_tasks)} Tasks")
    return {
        "count": tasks_data.get("count", 0),
        "tasks": filtered_tasks
    }

@task(name="Store Data")
def store_data(data, filename):
    """
    Store the combined data in a JSON file
    """
    logger = get_run_logger()
    
    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Create the file path
    file_path = data_dir / filename
    
    # Write the data to the file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Data successfully stored in {file_path}")
    return str(file_path)

@flow(name="Google Data ETL")
async def google_data_etl():
    """
    Main ETL flow that orchestrates the extraction, transformation, and loading of data
    """
    logger = get_run_logger()
    logger.info("Starting Google Data ETL flow")
    
    # Get today's date for the filename
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today}.json"
    
    # Extract data from Gmail, Calendar, and Tasks
    gmail_data = await fetch_gmail_messages()
    calendar_data = await fetch_calendar_events()
    tasks_data = await fetch_tasks()
    
    # Transform the data
    filtered_gmail = filter_gmail_data(gmail_data)
    filtered_calendar = filter_calendar_data(calendar_data)
    filtered_tasks = filter_tasks_data(tasks_data)
    
    # Combine all data
    combined_data = {
        "gmail": filtered_gmail,
        "calendar": filtered_calendar,
        "tasks": filtered_tasks,
        "extracted_at": datetime.now().isoformat()
    }
    
    # Load data to file
    file_path = store_data(combined_data, filename)
    
    logger.info(f"ETL process completed successfully. Data stored in {file_path}")
    return file_path

if __name__ == "__main__":
    import asyncio
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # Deploy the flow as a service
        # This will create a deployment with a schedule and start a worker to execute it
        from prefect.deployments import Deployment
        from prefect.server.schemas.schedules import CronSchedule
        
        deployment = google_data_etl.to_deployment(
            name="google-data-daily",
            description="Daily ETL job to extract Google data (Gmail, Calendar, Tasks)",
            version="1",
            tags=["daily", "google-data"],
            schedule=CronSchedule(
                cron="0 6 * * *",  # Run at 6:00 AM daily
                timezone="America/Los_Angeles"  # PST timezone
            ),
        )
        
        # Start the flow as a service
        google_data_etl.serve(
            name="google-data-daily",
            description="Daily ETL job to extract Google data (Gmail, Calendar, Tasks)",
            version="1",
            tags=["daily", "google-data"],
            schedule=CronSchedule(
                cron="0 6 * * *",  # Run at 6:00 AM daily
                timezone="America/Los_Angeles"  # PST timezone
            ),
        )
    else:
        # Run the flow directly
        asyncio.run(google_data_etl())