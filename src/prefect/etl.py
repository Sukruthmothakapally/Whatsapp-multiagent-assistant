from prefect import flow, task
from prefect.logging import get_run_logger
import httpx
import json
import os
from datetime import datetime
from pathlib import Path

# Base URL for the API
BASE_URL = "http://localhost:8000"  # Change if your server runs on a different port

# Increase timeout for HTTP requests
# This will give more time for API responses to be received
TIMEOUT_SECONDS = 30

@task(name="Fetch Gmail Messages", retries=3, retry_delay_seconds=5)
async def fetch_gmail_messages():
    """
    Fetch Gmail messages from the last 24 hours
    """
    logger = get_run_logger()
    logger.info("Fetching Gmail messages")
    
    try:
        # Use increased timeout to prevent ReadTimeout errors
        async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SECONDS)) as client:
            logger.info(f"Sending request to {BASE_URL}/api/google/gmail/me")
            response = await client.get(f"{BASE_URL}/api/google/gmail/me")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Gmail messages: {response.text}")
                raise Exception(f"Failed to fetch Gmail messages: {response.text}")
            
            data = response.json()
            logger.info(f"Successfully fetched {data.get('count', 0)} Gmail messages")
            return data
    except httpx.ReadTimeout:
        logger.error(f"Request timed out while fetching Gmail messages. Consider increasing timeout value.")
        raise
    except Exception as e:
        logger.error(f"Error fetching Gmail messages: {str(e)}")
        raise

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
    
    try:
        # Use increased timeout to prevent ReadTimeout errors
        async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SECONDS)) as client:
            logger.info(f"Sending request to {BASE_URL}/api/google/calendar/me")
            response = await client.get(f"{BASE_URL}/api/google/calendar/me")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Calendar events: {response.text}")
                raise Exception(f"Failed to fetch Calendar events: {response.text}")
            
            data = response.json()
            logger.info(f"Successfully fetched {data.get('count', 0)} Calendar events")
            return data
    except httpx.ReadTimeout:
        logger.error(f"Request timed out while fetching Calendar events. Consider increasing timeout value.")
        raise
    except Exception as e:
        logger.error(f"Error fetching Calendar events: {str(e)}")
        raise

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
    
    try:
        # Use increased timeout to prevent ReadTimeout errors
        async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SECONDS)) as client:
            logger.info(f"Sending request to {BASE_URL}/api/google/tasks/me")
            response = await client.get(f"{BASE_URL}/api/google/tasks/me")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Tasks: {response.text}")
                raise Exception(f"Failed to fetch Tasks: {response.text}")
            
            data = response.json()
            logger.info(f"Successfully fetched {data.get('count', 0)} Tasks")
            return data
    except httpx.ReadTimeout:
        logger.error(f"Request timed out while fetching Tasks. Consider increasing timeout value.")
        raise
    except Exception as e:
        logger.error(f"Error fetching Tasks: {str(e)}")
        raise

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
    
    try:
        # Extract data from Gmail, Calendar, and Tasks
        logger.info("Starting data extraction phase...")
        gmail_data = await fetch_gmail_messages()
        
        calendar_data = await fetch_calendar_events()
        
        tasks_data = await fetch_tasks()
        
        # Transform the data
        logger.info("Starting data transformation phase...")
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
        logger.info("Starting data loading phase...")
        file_path = store_data(combined_data, filename)
        
        logger.info(f"ETL process completed successfully. Data stored in {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"ETL process failed: {str(e)}")
        raise

if __name__ == "__main__":
    import asyncio
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # Deploy the flow as a service
        from prefect.server.schemas.schedules import CronSchedule
        
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
        print("Flow is now being served. Press Ctrl+C to stop.")
    else:
        # Run the flow directly
        print("Running Google Data ETL flow...")
        asyncio.run(google_data_etl())