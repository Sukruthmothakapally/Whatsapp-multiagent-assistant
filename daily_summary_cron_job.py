#!/usr/bin/env python
# daily_summary_cron_job.py - Place in project root folder

import requests
import logging
import datetime
import json
import time

# Configure logging with proper encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("daily_summary.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Your WhatsApp number that should receive the summary
RECIPIENT_PHONE = "16036884686" 

# API endpoint - looking at your webhook.py, the correct path is /webhook
API_URL = "https://a632-73-231-49-218.ngrok-free.app/webhook"

def trigger_daily_summary():
    """Trigger a daily summary by calling the FastAPI endpoint"""
    logger.info("Starting automated daily summary process")
    
    try:
        # Create a message payload that mimics a real WhatsApp message
        # Based on the structure expected by your webhook.py
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": RECIPIENT_PHONE,
                                        "id": f"daily_summary_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                                        "type": "text",
                                        "text": {
                                            "body": "Send me today's summary"
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        
        logger.info(f"Sending request to: {API_URL}")
        
        # Call your FastAPI endpoint with the correct payload format
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            logger.info(f"Daily summary request processed successfully")
            logger.info(f"Response: {response.text}")
            return True
        else:
            logger.error(f"Failed to process daily summary request: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        logger.error(f"Error in daily summary process: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    success = trigger_daily_summary()
    if success:
        logger.info("Daily summary cron job completed successfully")
    else:
        logger.error("Daily summary cron job failed")