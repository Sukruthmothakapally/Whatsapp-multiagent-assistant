import httpx
import os

# Get environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")

async def download_whatsapp_media(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    
    # Get media URL
    meta_url = f"https://graph.facebook.com/v18.0/{media_id}"
    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(meta_url, headers=headers)
        meta_resp.raise_for_status()
        media_url = meta_resp.json().get("url")
        
    # Download the file
    async with httpx.AsyncClient() as client:
        file_resp = await client.get(media_url, headers=headers)
        file_resp.raise_for_status()
        return file_resp.content